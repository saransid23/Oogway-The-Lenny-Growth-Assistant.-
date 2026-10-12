import re
import math
import logging
from typing import List, Tuple, Dict, Any, Optional
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
    - Filters common stop words for high-precision keyword overlap.
    - Supports metadata filtering (guest, topic).
    - Deduplicates overlapping / redundant chunks.
    - Provides retrieval diagnostics for debugging match relevance and thresholds.
    """

    def __init__(self, kb=None):
        self.kb = kb or knowledge_base

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

        # Attempt to get query embedding via Ollama nomic-embed-text
        query_embedding = self._get_query_embedding(query)

        scored_chunks: List[Tuple[TranscriptChunk, float]] = []
        for chunk in self.kb.chunks:
            # Metadata filter
            if guest_filter and guest_filter.lower() not in chunk.guest.lower():
                continue

            score = self._compute_score(query_terms, chunk, query_embedding)
            if score >= threshold:
                scored_chunks.append((chunk, score))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # Deduplicate overlapping chunks (keep highest-scoring chunk from each transcript section)
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

    def diagnose_query(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Provides retrieval diagnostics for debugging why certain chunks matched or failed to match."""
        cleaned_query = re.sub(r'[^\w\s]', '', query.lower())
        query_terms = [w for w in cleaned_query.split() if len(w) > 2 and w not in STOP_WORDS]
        query_embedding = self._get_query_embedding(query)

        evaluations = []
        for chunk in self.kb.chunks:
            kw_score = self._compute_keyword_score(query_terms, chunk)
            sem_score = 0.0
            if query_embedding and chunk.embedding:
                sem_score = self._cosine_similarity(query_embedding, chunk.embedding)
            total_score = self._compute_score(query_terms, chunk, query_embedding)
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

    def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        try:
            import urllib.request
            import json
            from app.config import settings
            req = urllib.request.Request(
                f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                data=json.dumps({
                    "model": settings.OLLAMA_EMBED_MODEL,
                    "prompt": query
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=2) as res:
                data = json.loads(res.read())
                return data.get("embedding")
        except Exception:
            return None

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

    def _compute_score(self, query_terms: List[str], chunk: TranscriptChunk, query_embedding: Optional[List[float]] = None) -> float:
        keyword_score = self._compute_keyword_score(query_terms, chunk)

        # Hybrid blend: 60% semantic + 40% keyword
        if query_embedding and chunk.embedding:
            semantic_score = self._cosine_similarity(query_embedding, chunk.embedding)
            # If zero keywords match and semantic score is below relatedness floor, treat as unrelated
            if keyword_score == 0.0 and semantic_score < 0.65:
                return 0.0
            final_score = (0.60 * semantic_score) + (0.40 * keyword_score)
            return min(final_score, 1.0)

        return keyword_score

    def _compute_keyword_score(self, query_terms: List[str], chunk: TranscriptChunk) -> float:
        matched_terms = 0
        total_weight = 0.0

        for term in query_terms:
            term_weight = 0.0
            if term in chunk.guest.lower():
                term_weight += 3.0
            if term in chunk.topic.lower():
                term_weight += 2.5
            if term in chunk.title.lower():
                term_weight += 2.0
            if term in chunk.text.lower():
                freq = chunk.text.lower().count(term)
                term_weight += min(freq * 0.5, 2.0)

            if term_weight > 0:
                matched_terms += 1
                total_weight += term_weight

        if matched_terms == 0:
            return 0.0

        overlap_ratio = matched_terms / len(query_terms)
        final_score = (total_weight / (len(query_terms) * 3.0)) * (0.5 + 0.5 * overlap_ratio)
        return min(final_score, 1.0)

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
