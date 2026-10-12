import os
import json
import re
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from app.config import settings

logger = logging.getLogger("lenny_assistant.knowledge_base")

class TranscriptChunk:
    def __init__(
        self,
        chunk_id: str,
        transcript_id: str,
        title: str,
        guest: str,
        date: str,
        source_url: str,
        timestamp: str,
        topic: str,
        text: str,
        content_hash: str = ""
    ):
        self.chunk_id = chunk_id
        self.transcript_id = transcript_id
        self.title = title
        self.guest = guest
        self.date = date
        self.source_url = source_url
        self.timestamp = timestamp
        self.topic = topic
        self.text = text
        self.content_hash = content_hash or self._compute_hash(text)
        self.tokens = self._tokenize(f"{title} {guest} {topic} {text}")
        self.embedding: Optional[List[float]] = None

    def _compute_hash(self, text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]

    def _tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r'[^\w\s]', '', text.lower())
        return [w for w in cleaned.split() if len(w) > 2]

class KnowledgeBase:
    """
    Transcript Knowledge Base & Ingestion Pipeline:
    - Incremental ingestion & idempotent duplicate detection.
    - Configurable text chunking with sliding overlap.
    - Metadata preservation (title, guest, date, source URL, timestamp, topic).
    - Cache invalidation and reporting of processed, skipped, and failed records.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or settings.TRANSCRIPTS_DIR
        self.chunks: List[TranscriptChunk] = []
        self._chunk_map: Dict[str, TranscriptChunk] = {}
        self._seen_hashes: set = set()
        self.load_transcripts()
        self.load_embeddings()

    def load_transcripts(self) -> Dict[str, Any]:
        """
        Loads all transcripts idempotently from disk, skipping duplicates.
        Returns detailed ingestion statistics.
        """
        self.chunks = []
        self._chunk_map = {}
        self._seen_hashes = set()

        stats = {
            "documents_processed": 0,
            "chunks_created": 0,
            "duplicates_skipped": 0,
            "failed": 0,
            "files_read": []
        }

        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            return stats

        for filename in sorted(os.listdir(self.data_dir)):
            if filename.endswith(".json") and not filename.startswith("."):
                filepath = os.path.join(self.data_dir, filename)
                try:
                    file_stats = self.ingest_file(filepath)
                    stats["documents_processed"] += file_stats["documents_processed"]
                    stats["chunks_created"] += file_stats["chunks_created"]
                    stats["duplicates_skipped"] += file_stats["duplicates_skipped"]
                    stats["failed"] += file_stats["failed"]
                    stats["files_read"].append(filename)
                except Exception as e:
                    logger.error(f"Error loading transcript file {filename}: {e}")
                    stats["failed"] += 1

        logger.info(f"Knowledge Base loaded: {len(self.chunks)} total chunks across {stats['documents_processed']} episodes.")
        return stats

    def ingest_file(self, filepath: str) -> Dict[str, int]:
        """Ingests a single transcript JSON file with validation and duplicate prevention."""
        stats = {"documents_processed": 0, "chunks_created": 0, "duplicates_skipped": 0, "failed": 0}
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        episodes = data if isinstance(data, list) else [data]
        for ep in episodes:
            try:
                ep_created, ep_skipped = self._process_episode(ep)
                stats["documents_processed"] += 1
                stats["chunks_created"] += ep_created
                stats["duplicates_skipped"] += ep_skipped
            except Exception as e:
                logger.warning(f"Error processing episode in {filepath}: {e}")
                stats["failed"] += 1

        return stats

    def _process_episode(self, ep: Dict[str, Any]) -> Tuple[int, int]:
        """Validates schema, segments content, and registers chunks idempotently."""
        t_id = ep.get("id") or f"ep-{hashlib.md5(ep.get('title', 'podcast').encode()).hexdigest()[:8]}"
        title = ep.get("title", "Lenny's Podcast")
        guest = ep.get("guest", "Podcast Guest")
        date = ep.get("date", "2023")
        source_url = ep.get("source_url", "https://www.lennyspodcast.com/")

        contents = ep.get("content", [])
        created = 0
        skipped = 0

        # Case 1: Structured sections list
        if isinstance(contents, list):
            for idx, item in enumerate(contents):
                if isinstance(item, dict):
                    text = item.get("text", "").strip()
                    topic = item.get("topic", "Growth Strategy")
                    timestamp = item.get("timestamp", "00:00")
                    c, s = self._add_chunk_or_split(
                        t_id=t_id,
                        chunk_idx=idx,
                        title=title,
                        guest=guest,
                        date=date,
                        source_url=source_url,
                        timestamp=timestamp,
                        topic=topic,
                        text=text
                    )
                    created += c
                    skipped += s
        # Case 2: Raw transcript string
        elif isinstance(contents, str) and len(contents.strip()) > 0:
            c, s = self._chunk_long_text(
                t_id=t_id,
                title=title,
                guest=guest,
                date=date,
                source_url=source_url,
                raw_text=contents.strip()
            )
            created += c
            skipped += s

        return created, skipped

    def _add_chunk_or_split(
        self,
        t_id: str,
        chunk_idx: int,
        title: str,
        guest: str,
        date: str,
        source_url: str,
        timestamp: str,
        topic: str,
        text: str
    ) -> Tuple[int, int]:
        if not text:
            return 0, 0

        # If text is exceptionally long (> 1000 characters), split with overlap
        if len(text) > 1200:
            return self._chunk_long_text(
                t_id=f"{t_id}-{chunk_idx}",
                title=title,
                guest=guest,
                date=date,
                source_url=source_url,
                raw_text=text,
                topic=topic,
                timestamp=timestamp
            )

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        if content_hash in self._seen_hashes:
            return 0, 1  # Duplicate skipped

        chunk_id = f"{t_id}-{chunk_idx}"
        chunk = TranscriptChunk(
            chunk_id=chunk_id,
            transcript_id=t_id,
            title=title,
            guest=guest,
            date=date,
            source_url=source_url,
            timestamp=timestamp,
            topic=topic,
            text=text,
            content_hash=content_hash
        )
        self.chunks.append(chunk)
        self._chunk_map[chunk_id] = chunk
        self._seen_hashes.add(content_hash)
        return 1, 0

    def _chunk_long_text(
        self,
        t_id: str,
        title: str,
        guest: str,
        date: str,
        source_url: str,
        raw_text: str,
        topic: str = "Growth Strategy",
        timestamp: str = "00:00",
        chunk_size: int = 800,
        chunk_overlap: int = 150
    ) -> Tuple[int, int]:
        words = raw_text.split()
        if not words:
            return 0, 0

        step = max(50, chunk_size - chunk_overlap)
        created = 0
        skipped = 0

        for i in range(0, len(words), step):
            sub_words = words[i:i + chunk_size]
            sub_text = " ".join(sub_words)
            content_hash = hashlib.sha256(sub_text.encode("utf-8")).hexdigest()[:16]

            if content_hash in self._seen_hashes:
                skipped += 1
                continue

            sub_chunk_id = f"{t_id}-sub-{i // step}"
            chunk = TranscriptChunk(
                chunk_id=sub_chunk_id,
                transcript_id=t_id,
                title=title,
                guest=guest,
                date=date,
                source_url=source_url,
                timestamp=timestamp,
                topic=topic,
                text=sub_text,
                content_hash=content_hash
            )
            self.chunks.append(chunk)
            self._chunk_map[sub_chunk_id] = chunk
            self._seen_hashes.add(content_hash)
            created += 1

        return created, skipped

    def load_embeddings(self):
        """Loads cached embeddings with hash verification; generates embeddings if Ollama available."""
        cache_path = os.path.join(self.data_dir, ".embeddings_cache.json")
        cached = {}
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
            except Exception:
                pass

        missing_chunks = []
        for chunk in self.chunks:
            if chunk.chunk_id in cached:
                cached_val = cached[chunk.chunk_id]
                if isinstance(cached_val, list):
                    chunk.embedding = cached_val
                elif isinstance(cached_val, dict) and cached_val.get("hash") == chunk.content_hash:
                    chunk.embedding = cached_val.get("embedding")
                else:
                    missing_chunks.append(chunk)
            else:
                missing_chunks.append(chunk)

        # Attempt to generate embeddings for missing chunks
        if missing_chunks:
            try:
                import urllib.request
                for chunk in missing_chunks[:20]:  # Batch bounded to avoid blocking startup
                    embed_text = f"{chunk.guest} - {chunk.topic}: {chunk.text}"
                    req = urllib.request.Request(
                        f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                        data=json.dumps({
                            "model": settings.OLLAMA_EMBED_MODEL,
                            "prompt": embed_text
                        }).encode(),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=3) as res:
                        data = json.loads(res.read())
                        emb = data.get("embedding")
                        if emb:
                            chunk.embedding = emb
                            cached[chunk.chunk_id] = {
                                "hash": chunk.content_hash,
                                "embedding": emb
                            }

                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cached, f)
            except Exception:
                pass

    def invalidate_cache(self):
        """Invalidates embeddings cache when documents change."""
        cache_path = os.path.join(self.data_dir, ".embeddings_cache.json")
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except Exception as e:
                logger.warning(f"Failed to remove cache file: {e}")
        self.load_transcripts()
        self.load_embeddings()

knowledge_base = KnowledgeBase()
