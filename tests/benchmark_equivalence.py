import time
import math
import random
import numpy as np
from app.rag.knowledge_base import KnowledgeBase, TranscriptChunk
from app.rag.retriever import TranscriptRetriever, retriever

def run_equivalence_and_speed_benchmark():
    print("=" * 65)
    print(">> RUNNING RETRIEVAL EQUIVALENCE & VECTORIZATION BENCHMARK")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. Real Transcripts Keyword Equivalence
    # -------------------------------------------------------------
    print("[*] 1. Keyword-Only Equivalence on Real Transcripts:")
    queries = [
        "Shreyas Doshi LNO framework",
        "Elena Verna product led growth loops",
        "Marty Cagan product discovery risks"
    ]
    for q in queries:
        cleaned = [w for w in q.lower().split() if len(w) > 2]
        scores_old = []
        scores_new = []
        for chunk in retriever.kb.chunks:
            # Old way: inline .lower()
            matched_terms = 0
            total_weight = 0.0
            for term in cleaned:
                w = 0.0
                if term in chunk.guest.lower(): w += 3.0
                if term in chunk.topic.lower(): w += 2.5
                if term in chunk.title.lower(): w += 2.0
                if term in chunk.text.lower(): w += min(chunk.text.lower().count(term) * 0.5, 2.0)
                if w > 0:
                    matched_terms += 1
                    total_weight += w
            raw_old = (total_weight / (len(cleaned) * 3.0)) * (0.5 + 0.5 * (matched_terms / len(cleaned))) if matched_terms > 0 else 0.0
            s_old = min(raw_old, 1.0)
            
            # New way: precomputed lowercase
            s_new = retriever._compute_keyword_score(cleaned, chunk)
            scores_old.append(s_old)
            scores_new.append(s_new)

        max_diff = max(abs(a - b) for a, b in zip(scores_old, scores_new))
        assert max_diff < 1e-6, f"Keyword discrepancy for '{q}': max diff {max_diff}"
        print(f"   - Query: '{q}': IDENTICAL (max diff = {max_diff:.1e})")

    # -------------------------------------------------------------
    # 2. Synthetic 3,000 chunks x 768 dims Equivalence & Latency
    # -------------------------------------------------------------
    print()
    print("[*] 2. Synthetic Benchmark (3,000 chunks x 768 dimensions):")
    n_chunks = 3000
    dim = 768
    rng = random.Random(42)

    synthetic_kb = KnowledgeBase.__new__(KnowledgeBase)
    synthetic_kb.data_dir = "data/transcripts"
    synthetic_kb._seen_hashes = set()
    synthetic_kb._chunk_map = {}
    synthetic_kb._matrix = None
    synthetic_kb._matrix_indices = []
    synthetic_kb._embedding_dim = None
    synthetic_kb._indexed_chunk_count = None
    synthetic_kb.chunks = []

    for i in range(n_chunks):
        c = TranscriptChunk(
            chunk_id=f"syn_{i}",
            transcript_id=f"t_{i // 50}",
            title=f"Episode {i}",
            guest=f"Guest {i % 10}",
            date="2023",
            source_url="https://example.com",
            timestamp="10:00",
            topic="Growth",
            text=f"Synthetic text sample {i}"
        )
        # Random embedding normalized
        raw_vec = [rng.gauss(0, 1) for _ in range(dim)]
        norm = math.sqrt(sum(x * x for x in raw_vec))
        c.embedding = [x / norm for x in raw_vec]
        synthetic_kb.chunks.append(c)

    q_vec = [rng.gauss(0, 1) for _ in range(dim)]
    q_norm = math.sqrt(sum(x * x for x in q_vec))
    q_vec = [x / q_norm for x in q_vec]

    # Measure Old Pure-Python Cosine Loop
    t0 = time.perf_counter()
    scores_py = []
    for chunk in synthetic_kb.chunks:
        dot = sum(a * b for a, b in zip(q_vec, chunk.embedding))
        scores_py.append(max(0.0, min(dot, 1.0)))
    top3_py_indices = sorted(range(n_chunks), key=lambda i: scores_py[i], reverse=True)[:3]
    t_py = (time.perf_counter() - t0) * 1000

    # Measure New Vectorized NumPy Matrix
    # Warmup / ensure index
    synthetic_kb._ensure_index()
    t0 = time.perf_counter()
    res_vec = synthetic_kb.semantic_scores(q_vec)
    scores_vec, _ = res_vec
    top3_vec_indices = sorted(range(n_chunks), key=lambda i: scores_vec[i], reverse=True)[:3]
    t_vec = (time.perf_counter() - t0) * 1000

    print(f"   - Top 3 Chunk IDs (Pure Python): {[synthetic_kb.chunks[i].chunk_id for i in top3_py_indices]}")
    print(f"   - Top 3 Chunk IDs (Vectorized):  {[synthetic_kb.chunks[i].chunk_id for i in top3_vec_indices]}")
    assert top3_py_indices == top3_vec_indices, "Top 3 chunk ranking must be identical!"

    top3_py_scores = [scores_py[i] for i in top3_py_indices]
    top3_vec_scores = [float(scores_vec[i]) for i in top3_vec_indices]
    print(f"   - Top 3 Scores (Pure Python): {[round(s, 5) for s in top3_py_scores]}")
    print(f"   - Top 3 Scores (Vectorized):  {[round(s, 5) for s in top3_vec_scores]}")

    max_score_diff = max(abs(a - b) for a, b in zip(top3_py_scores, top3_vec_scores))
    assert max_score_diff < 2e-3, f"Scores must match within tolerance 2e-3, got {max_score_diff}"

    speedup = t_py / t_vec if t_vec > 0 else 0
    print()
    print(f"[*] 3. Performance Comparison (3,000 chunks):")
    print(f"   - Pure-Python Cosine: {t_py:.2f} ms")
    print(f"   - NumPy Vectorized:   {t_vec:.2f} ms")
    print(f"   - Speedup Factor:     {speedup:.1f}x faster")
    print("=" * 65)

    return {
        "t_py_ms": t_py,
        "t_vec_ms": t_vec,
        "speedup": speedup,
        "max_score_diff": max_score_diff
    }

if __name__ == "__main__":
    run_equivalence_and_speed_benchmark()
