# Demo Video Recording Guide & Script (2–3 Minutes)

> **Assignment Requirement**: Record a 2–3 minute video with camera enabled explaining the problem, demonstrating the product, showing local Ollama, and covering an important technical trade-off.

---

## ⏱️ Video Cue Sheet & Timestamp Breakdown

| Timestamp | Segment | Visual / Screen Action | Spoken Talking Points |
|:---|:---|:---|:---|
| **0:00 - 0:35** | **1. Problem & Context** | Full face camera, then transition to browser at `http://localhost:8000` | "Hi everyone. Lenny’s Podcast contains hundreds of hours of high-leverage product frameworks from guests like Shreyas Doshi, Elena Verna, and Marty Cagan. But PMs and founders can’t scrub 90-minute episodes when solving problems in their daily work. Today I'm demonstrating **The Lenny Growth Assistant**—a production-grade, full-stack application built to deliver grounded transcript intelligence, write Ship 30 essays, and render live artifacts in an isolated sandbox." |
| **0:35 - 1:15** | **2. Grounded RAG & Citations** | Click prompt card *"Explain Shreyas Doshi's LNO framework"* | "Notice our conversation interface. When I ask about Shreyas Doshi's LNO framework, the system uses a TF-IDF keyword retriever against chunked transcript data. Rather than hallucinating generic advice, every single key claim is cited with the guest's name, timestamp, and clickable transcript quotes shown right here in these citation pills." |
| **1:15 - 1:45** | **3. Local Ollama & Model Toggle** | Highlight sidebar "Execution Engine", toggle Local (Ollama) vs Cloud | "A core requirement was complete evaluator flexibility. In the sidebar, you can toggle between **Local (Ollama)** running Mistral or Llama on the machine, and **Cloud LLM** providers like OpenAI or Anthropic. If Ollama is paused and cloud keys aren't configured, our smart RAG fallback engine activates automatically so the evaluator's workflow is never interrupted." |
| **1:45 - 2:20** | **4. Ship 30 Skill & Live Artifacts** | Click *"Ship 30 Skill"* button, then prompt an HTML dashboard artifact | "We also implemented dedicated skills. The Ship 30 for 30 button synthesizes a hyper-skimmable ~1,250-word masterclass with strong hooks, narrative progression, and grounded takeaways. Furthermore, when generating HTML or dashboard mockups, our side-by-side Artifact Viewer slides open. Users can inspect the code, preview the live component, and copy it with one click." |
| **2:20 - 2:50** | **5. Key Technical Trade-off** | Show DevTools inspecting iframe sandbox attribute | "For our key technical trade-off: **Artifact Security**. Executing arbitrary LLM-generated HTML in the host window creates severe XSS and session hijacking risks. We solved this by hosting the preview in a sandboxed iframe with `sandbox='allow-scripts'`, deliberately omitting `allow-same-origin`. This gives the rendered artifact complete interactivity while strictly isolating host cookies, parent DOM, and local storage." |
| **2:50 - 3:00** | **6. Wrap-up & Operability** | Terminal running `docker compose up` or `pytest -v` | "The entire stack is containerized with Docker Compose, tested with an automated pytest suite, and ready for immediate evaluation. Thanks for watching!" |

---

## 🎬 Recording & Submission Checklist
- [ ] Camera enabled (picture-in-picture in corner of screen recording e.g. Loom, OBS, or Zoom).
- [ ] Application running locally via `python run.py` at `http://localhost:8000`.
- [ ] Terminal window open showing test suite `pytest -v` passing.
- [ ] Upload video to YouTube (Unlisted or Public).
- [ ] Paste YouTube link into the submission form: `https://forms.gle/LgotDHNVxW1mbzNE7`.
