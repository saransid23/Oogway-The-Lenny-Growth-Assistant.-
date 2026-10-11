import os
import json
import re
import math
from typing import List, Dict, Any
from app.config import settings

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
        text: str
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
        self.tokens = self._tokenize(f"{title} {guest} {topic} {text}")
        self.embedding = None

    def _tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r'[^\w\s]', '', text.lower())
        return [w for w in cleaned.split() if len(w) > 2]

class KnowledgeBase:
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or settings.TRANSCRIPTS_DIR
        self.chunks: List[TranscriptChunk] = []
        self.load_transcripts()
        self.load_embeddings()

    def load_transcripts(self):
        self.chunks = []
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            return

        for filename in sorted(os.listdir(self.data_dir)):
            if filename.endswith(".json") and not filename.startswith("."):
                filepath = os.path.join(self.data_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for ep in data:
                                self._process_episode(ep)
                except Exception as e:
                    print(f"Error loading transcript file {filename}: {e}")

    def load_embeddings(self):
        """Loads cached chunk embeddings or computes them using Ollama nomic-embed-text."""
        cache_path = os.path.join(self.data_dir, ".embeddings_cache.json")
        cached = {}
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
            except Exception:
                pass

        # Apply existing cached embeddings
        missing_chunks = []
        for chunk in self.chunks:
            if chunk.chunk_id in cached:
                chunk.embedding = cached[chunk.chunk_id]
            else:
                missing_chunks.append(chunk)

        # Attempt to generate embeddings for missing chunks if Ollama is accessible
        if missing_chunks:
            try:
                import urllib.request
                for chunk in missing_chunks:
                    embed_text = f"{chunk.guest} - {chunk.topic}: {chunk.text}"
                    req = urllib.request.Request(
                        f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                        data=json.dumps({
                            "model": settings.OLLAMA_EMBED_MODEL,
                            "prompt": embed_text
                        }).encode(),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=5) as res:
                        data = json.loads(res.read())
                        emb = data.get("embedding")
                        if emb:
                            chunk.embedding = emb
                            cached[chunk.chunk_id] = emb

                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cached, f)
            except Exception:
                # Graceful fallback: chunks operate with keyword indexing
                pass

    def _process_episode(self, ep: Dict[str, Any]):
        t_id = ep.get("id", "lenny-ep")
        title = ep.get("title", "Lenny's Podcast")
        guest = ep.get("guest", "Podcast Guest")
        date = ep.get("date", "2023")
        source_url = ep.get("source_url", "https://www.lennyspodcast.com/")
        
        contents = ep.get("content", [])
        for idx, item in enumerate(contents):
            chunk = TranscriptChunk(
                chunk_id=f"{t_id}-{idx}",
                transcript_id=t_id,
                title=title,
                guest=guest,
                date=date,
                source_url=source_url,
                timestamp=item.get("timestamp", "00:00"),
                topic=item.get("topic", "Growth Strategy"),
                text=item.get("text", "")
            )
            self.chunks.append(chunk)

# Global singleton instance
knowledge_base = KnowledgeBase()
