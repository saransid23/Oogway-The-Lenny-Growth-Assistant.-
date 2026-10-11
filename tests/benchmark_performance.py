import time
import json
import urllib.request
from app.rag.retriever import retriever

def run_performance_benchmarks():
    print("=" * 65)
    print(">> THE LENNY GROWTH ASSISTANT -- MODEL & RAG BENCHMARK")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. Embedding Model Latency (nomic-embed-text)
    # -------------------------------------------------------------
    t0 = time.perf_counter()
    req = urllib.request.Request(
        "http://localhost:11434/api/embeddings",
        data=json.dumps({"model": "nomic-embed-text", "prompt": "What is product-led growth and user acquisition loops?"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        emb_data = json.loads(res.read())
    t_embed = (time.perf_counter() - t0) * 1000
    emb_dim = len(emb_data.get("embedding", []))
    print(f"[*] 1. Vector Embedding Latency (nomic-embed-text):")
    print(f"   - Latency: {t_embed:.2f} ms")
    print(f"   - Vector Dimension: {emb_dim} float32 numbers")
    print()

    # -------------------------------------------------------------
    # 2. Hybrid RAG Retrieval Speed (Embeddings + Lexical TF-IDF)
    # -------------------------------------------------------------
    test_queries = [
        "Explain Shreyas Doshi LNO framework",
        "Elena Verna on PLG vs PLS",
        "Marty Cagan 4 product discovery risks"
    ]
    print("[*] 2. Hybrid RAG Retrieval Accuracy & Speed:")
    for q in test_queries:
        t0 = time.perf_counter()
        chunks, citations = retriever.search(q, top_k=3)
        t_search = (time.perf_counter() - t0) * 1000
        top_guest = citations[0].guest if citations else "None"
        top_score = citations[0].score if citations else 0.0
        print(f"   - Query: \"{q}\"")
        print(f"     Match: {top_guest} | Score: {top_score} | Citations: {len(citations)} | Latency: {t_search:.2f} ms")
    print()

    # -------------------------------------------------------------
    # 3. Local LLM Generation Speed (Mistral 7B)
    # -------------------------------------------------------------
    print("[*] 3. Local LLM Inference Performance (Mistral 7B via Ollama):")
    t0 = time.perf_counter()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps({
            "model": "mistral",
            "prompt": "In 3 concise bullet points, explain what makes the LNO framework effective for product managers.",
            "stream": False
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        gen_data = json.loads(res.read())
    t_gen = time.perf_counter() - t0
    reply = gen_data.get("response", "").strip()
    word_count = len(reply.split())
    tokens_est = int(word_count * 1.33)
    tok_per_sec = tokens_est / t_gen if t_gen > 0 else 0
    print(f"   - Total Generation Time: {t_gen:.2f} s")
    print(f"   - Words Generated: {word_count} words (~{tokens_est} tokens)")
    print(f"   - Generation Throughput: ~{tok_per_sec:.1f} tokens/second")
    print()

    # -------------------------------------------------------------
    # 4. End-to-End Chat API Response (/api/chat)
    # -------------------------------------------------------------
    print("[*] 4. End-to-End User Experience (/api/chat endpoint):")
    t0 = time.perf_counter()
    req = urllib.request.Request(
        "http://localhost:8000/api/chat",
        data=json.dumps({
            "message": "Give me a quick 2-bullet summary of Elena Verna's views on B2B PLG.",
            "provider": "local"
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        chat_data = json.loads(res.read())
    t_chat = time.perf_counter() - t0
    c_count = len(chat_data.get("citations", []))
    rep_len = len(chat_data.get("reply", ""))
    print(f"   - End-to-End Request Latency: {t_chat:.2f} s")
    print(f"   - Citations Attached: {c_count}")
    print(f"   - Response Length: {rep_len} characters")
    print("=" * 65)

if __name__ == "__main__":
    run_performance_benchmarks()
