import re
import math
import time
import logging
from collections import OrderedDict
from typing import List, Tuple, Dict, Any, Optional
from app.config import settings
from app.rag.knowledge_base import knowledge_base, TranscriptChunk
from app.models import Citation

logger = logging.getLogger("lenny_assistant.retriever")

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
}

class TranscriptRetriever:
    """
    Hybrid Transcript Retriever:
    - Combines semantic cosine similarity (using nomic-embed-text) with weighted keyword matching.
    - Non-blocking async retrieval (asearch) and synchronous retrieval (search).
    - LRU embedding query cache and failure back-off circuit breaker.
    - Vectorized matrix scoring via knowledge base.
    """

    def __init__(self, kb=None):
        self.kb = kb or knowledge_base
        self._embed_cache: OrderedDict[str, List[float]] = OrderedDict()
        self._last_embed_failure: float = 0.0

    def _normalize_key(self, query: str) -> str:
        return " ".join(query.lower().strip().split())

    def _check_cache(self, key: str) -> Optional[List[float]]:
        if key in self._embed_cache:
            self._embed_cache.move_to_end(key)
            return self._embed_cache[key]
        return None

    def _save_cache(self, key: str, embedding: List[float]):
        self._embed_cache[key] = embedding
        self._embed_cache.move_to_end(key)
        while len(self._embed_cache) > settings.EMBED_CACHE_SIZE:
            self._embed_cache.popitem(last=False)

    def _is_backing_off(self) -> bool:
        return (time.time() - self._last_embed_failure) < settings.EMBED_BACKOFF_SECONDS

    def _record_failure(self):
        self._last_embed_failure = time.time()

    def _get_query_embedding_sync(self, query: str) -> Optional[List[float]]:
        key = self._normalize_key(query)
        cached = self._check_cache(key)
        if cached is not None:
            return cached

        if self._is_backing_off():
            return None

        try:
            import urllib.request
            import json
            req = urllib.request.Request(
                f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                data=json.dumps({
                    "model": settings.OLLAMA_EMBED_MODEL,
                    "prompt": query,
                    "keep_alive": settings.OLLAMA_KEEP_ALIVE
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=settings.EMBED_TIMEOUT_SECONDS) as res:
                if res.status == 200:
                    data = json.loads(res.read())
                    emb = data.get("embedding")
                    if emb:
                        self._save_cache(key, emb)
                        return emb
            self._record_failure()
            return None
        except Exception:
            self._record_failure()
            return None

    async def _get_query_embedding_async(self, query: str) -> Optional[List[float]]:
        key = self._normalize_key(query)
        cached = self._check_cache(key)
        if cached is not None:
            return cached

        if self._is_backing_off():
            return None

        try:
            from app.llm.ollama_client import ollama_client
            emb = await ollama_client.embed(query)
            if emb:
                self._save_cache(key, emb)
                return emb
            self._record_failure()
            return None
        except Exception:
            self._record_failure()
            return None

    def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """Backwards-compatible synchronous query embedding getter."""
        return self._get_query_embedding_sync(query)

    def _compute_keyword_score(self, query_terms: List[str], chunk: TranscriptChunk) -> float:
        matched_terms = 0
        total_weight = 0.0

        for term in query_terms:
            term_weight = 0.0
            if term in chunk.guest_lower:
                term_weight += 3.0
            if term in chunk.topic_lower:
                term_weight += 2.5
            if term in chunk.title_lower:
                term_weight += 2.0
            if term in chunk.text_lower:
                freq = chunk.text_lower.count(term)
                term_weight += min(freq * 0.5, 2.0)

            if term_weight > 0:
                matched_terms += 1
                total_weight += term_weight

        if matched_terms == 0:
            return 0.0

        overlap_ratio = matched_terms / len(query_terms)
        final_score = (total_weight / (len(query_terms) * 3.0)) * (0.5 + 0.5 * overlap_ratio)
        return min(final_score, 1.0)

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return max(0.0, min(dot / (norm_a * norm_b), 1.0))

    def _rank(
        self,
        query: str,
        query_terms: List[str],
        query_embedding: Optional[List[float]],
        top_k: int = 3,
        threshold: float = 0.08,
        guest_filter: Optional[str] = None
    ) -> Tuple[List[TranscriptChunk], List[Citation]]:
        guest_filter_lower = guest_filter.lower() if guest_filter else None

        sem_result = self.kb.semantic_scores(query_embedding)
        has_vector_scores = sem_result is not None
        sem_scores, has_score = sem_result if has_vector_scores else (None, None)

        scored_chunks: List[Tuple[TranscriptChunk, float]] = []
        for idx, chunk in enumerate(self.kb.chunks):
            if guest_filter_lower and guest_filter_lower not in chunk.guest_lower:
                continue

            kw_score = self._compute_keyword_score(query_terms, chunk)

            if has_vector_scores and has_score[idx]:
                sem_score = float(sem_scores[idx])
                if kw_score == 0.0 and sem_score < 0.65:
                    score = 0.0
                else:
                    score = min((0.60 * sem_score) + (0.40 * kw_score), 1.0)
            else:
                score = kw_score

            if score >= threshold:
                scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        deduped_chunks: List[Tuple[TranscriptChunk, float]] = []
        seen_section_signatures = set()
        for chunk, score in scored_chunks:
            sig = f"{chunk.transcript_id}-{chunk.timestamp}"
            if sig not in seen_section_signatures:
                seen_section_signatures.add(sig)
                deduped_chunks.append((chunk, score))
            if len(deduped_chunks) >= top_k:
                break

        citations: List[Citation] = []
        result_chunks: List[TranscriptChunk] = []
        for chunk, score in deduped_chunks:
            result_chunks.append(chunk)
            citations.append(
                Citation(
                    transcript_id=chunk.transcript_id,
                    guest=chunk.guest,
                    title=chunk.title,
                    timestamp=chunk.timestamp,
                    topic=chunk.topic,
                    quote=chunk.text[:220] + "..." if len(chunk.text) > 220 else chunk.text,
                    source_url=chunk.source_url,
                    score=round(score, 3)
                )
            )

        return result_chunks, citations

    def search(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.08,
        guest_filter: Optional[str] = None
    ) -> Tuple[List[TranscriptChunk], List[Citation]]:
        cleaned_query = re.sub(r'[^\w\s]', '', query.lower())
        query_terms = [w for w in cleaned_query.split() if len(w) > 2 and w not in STOP_WORDS]
        if not query_terms:
            return [], []

        query_embedding = self._get_query_embedding_sync(query)
        return self._rank(query, query_terms, query_embedding, top_k, threshold, guest_filter)

    async def asearch(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.08,
        guest_filter: Optional[str] = None
    ) -> Tuple[List[TranscriptChunk], List[Citation]]:
        cleaned_query = re.sub(r'[^\w\s]', '', query.lower())
        query_terms = [w for w in cleaned_query.split() if len(w) > 2 and w not in STOP_WORDS]
        if not query_terms:
            return [], []

        query_embedding = await self._get_query_embedding_async(query)
        return self._rank(query, query_terms, query_embedding, top_k, threshold, guest_filter)

    def diagnose_query(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Provides retrieval diagnostics for debugging why certain chunks matched or failed to match."""
        cleaned_query = re.sub(r'[^\w\s]', '', query.lower())
        query_terms = [w for w in cleaned_query.split() if len(w) > 2 and w not in STOP_WORDS]
        query_embedding = self._get_query_embedding_sync(query)

        sem_result = self.kb.semantic_scores(query_embedding)
        has_vector_scores = sem_result is not None
        sem_scores, has_score = sem_result if has_vector_scores else (None, None)

        evaluations = []
        for idx, chunk in enumerate(self.kb.chunks):
            kw_score = self._compute_keyword_score(query_terms, chunk)
            sem_score = 0.0
            if has_vector_scores and has_score[idx]:
                sem_score = float(sem_scores[idx])

            if has_vector_scores and has_score[idx]:
                if kw_score == 0.0 and sem_score < 0.65:
                    total_score = 0.0
                else:
                    total_score = min((0.60 * sem_score) + (0.40 * kw_score), 1.0)
            else:
                total_score = kw_score

            evaluations.append({
                "chunk_id": chunk.chunk_id,
                "guest": chunk.guest,
                "topic": chunk.topic,
                "keyword_score": round(kw_score, 4),
                "semantic_score": round(sem_score, 4),
                "combined_score": round(total_score, 4)
            })

        evaluations.sort(key=lambda x: x["combined_score"], reverse=True)

        return {
            "query": query,
            "query_terms": query_terms,
            "has_query_embedding": bool(query_embedding),
            "total_candidates_evaluated": len(self.kb.chunks),
            "top_candidates": evaluations[:top_k]
        }

    def format_rag_context(self, chunks: List[TranscriptChunk]) -> str:
        if not chunks:
            return "No direct Lenny's Podcast transcript match found for this specific query."

        context_str = "LENNY'S PODCAST TRANSCRIPT KNOWLEDGE BASE CONTEXT:\n"
        for idx, chunk in enumerate(chunks, 1):
            context_str += f"\n[SOURCE {idx}]\n"
            context_str += f"Guest: {chunk.guest}\n"
            context_str += f"Episode Title: {chunk.title}\n"
            context_str += f"Topic/Timestamp: {chunk.topic} ({chunk.timestamp})\n"
            context_str += f"Transcript Excerpt:\n\"{chunk.text}\"\n"

        return context_str

retriever = TranscriptRetriever()
