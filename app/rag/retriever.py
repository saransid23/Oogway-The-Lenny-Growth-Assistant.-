import re
import math
from typing import List, Tuple
from app.rag.knowledge_base import knowledge_base, TranscriptChunk
from app.models import Citation

class TranscriptRetriever:
    def __init__(self, kb=None):
        self.kb = kb or knowledge_base

    def search(self, query: str, top_k: int = 3, threshold: float = 0.05) -> Tuple[List[TranscriptChunk], List[Citation]]:
        cleaned_query = re.sub(r'[^\w\s]', '', query.lower())
        query_terms = [w for w in cleaned_query.split() if len(w) > 2]
        
        if not query_terms:
            return [], []

        # Attempt to get query embedding via Ollama nomic-embed-text
        query_embedding = self._get_query_embedding(query)

        scored_chunks = []
        for chunk in self.kb.chunks:
            score = self._compute_score(query_terms, chunk, query_embedding)
            if score >= threshold:
                scored_chunks.append((chunk, score))

        # Sort by score descending
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        top_chunks = scored_chunks[:top_k]

        citations = []
        result_chunks = []
        for chunk, score in top_chunks:
            result_chunks.append(chunk)
            citations.append(
                Citation(
                    transcript_id=chunk.transcript_id,
                    guest=chunk.guest,
                    title=chunk.title,
                    timestamp=chunk.timestamp,
                    topic=chunk.topic,
                    quote=chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
                    source_url=chunk.source_url,
                    score=round(score, 3)
                )
            )

        return result_chunks, citations

    def _get_query_embedding(self, query: str) -> List[float]:
        """Fetch query vector embedding from Ollama nomic-embed-text."""
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
            with urllib.request.urlopen(req, timeout=3) as res:
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

    def _compute_score(self, query_terms: List[str], chunk: TranscriptChunk, query_embedding: List[float] = None) -> float:
        keyword_score = self._compute_keyword_score(query_terms, chunk)

        # Hybrid blend: 60% semantic similarity + 40% keyword precision
        if query_embedding and chunk.embedding:
            semantic_score = self._cosine_similarity(query_embedding, chunk.embedding)
            final_score = (0.60 * semantic_score) + (0.40 * keyword_score)
            return min(final_score, 1.0)

        return keyword_score

    def _compute_keyword_score(self, query_terms: List[str], chunk: TranscriptChunk) -> float:
        # Match against tokens in topic, title, guest, and text
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
