import time
import json
from fastapi.testclient import TestClient
from app.main import app

def measure():
    client = TestClient(app)
    query = "In 2 sentences, explain Shreyas Doshi's LNO framework."

    print("=" * 65)
    print(">> MEASURING TIME-TO-FIRST-TOKEN (TTFT) VS NON-STREAMING LATENCY")
    print("=" * 65)

    # 1. Streaming TTFT
    print("[*] 1. Streaming /api/chat/stream:")
    t0 = time.perf_counter()
    ttft = None
    token_count = 0
    total_stream = None

    with client.stream("POST", "/api/chat/stream", json={"message": query, "provider": "local"}) as res:
        for line in res.iter_lines():
            if line.startswith("event: token") and ttft is None:
                ttft = time.perf_counter() - t0
            if line.startswith("data:") and ttft is not None:
                token_count += 1
        total_stream = time.perf_counter() - t0

    print(f"   - Time to First Token (TTFT): {ttft:.2f} s")
    print(f"   - Total Stream Time:         {total_stream:.2f} s")

    # 2. Non-streaming /api/chat
    print()
    print("[*] 2. Non-Streaming /api/chat:")
    t0 = time.perf_counter()
    res = client.post("/api/chat", json={"message": query, "provider": "local"})
    total_sync = time.perf_counter() - t0
    print(f"   - Status Code:               {res.status_code}")
    print(f"   - End-to-End Latency:        {total_sync:.2f} s")

    perceived_speedup = total_sync / ttft if (ttft and ttft > 0) else 0
    print()
    print(f"[*] Perceived Latency Improvement (Wait time until response begins):")
    print(f"   - Before (Non-streaming user wait): {total_sync:.2f} s")
    print(f"   - After  (Streaming user TTFT):    {ttft:.2f} s")
    print(f"   - Perceived Speedup Factor:         {perceived_speedup:.1f}x faster to first feedback")
    print("=" * 65)

if __name__ == "__main__":
    measure()
