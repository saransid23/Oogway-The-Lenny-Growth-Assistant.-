# UI Manual Test Plan — The Lenny Growth Assistant

This document outlines the step-by-step manual test cases to verify the end-to-end functionality, user experience, and security of The Lenny Growth Assistant.

---

## Pre-requisites
1. Start the application backend:
   ```bash
   python run.py
   ```
2. Open browser at: `http://localhost:8000`

---

## Test Scenarios

### Test Case 1: System Boot & Initial State
- **Objective**: Verify that the application boots cleanly and initializes state.
- **Steps**:
  1. Navigate to `http://localhost:8000`.
  2. Observe the Left Sidebar, Top Header, and Welcome Hero.
- **Expected Results**:
  - Sidebar shows brand mark, "New Conversation" button with `Ctrl+N` indicator.
  - Footer shows active RAG status (`RAG: 15 Transcript Chunks` or active count).
  - Welcome Hero displays Lenny's Growth Assistant greeting with 4 starter prompt cards.
  - Pass/Fail: Pass.

---

### Test Case 2: Grounded RAG Conversation & Citations
- **Objective**: Verify that answers are grounded in Lenny's podcast transcripts with clickable citations.
- **Steps**:
  1. Click the prompt card: *"Explain Shreyas Doshi's LNO framework and how to apply it to PM task management."*
  2. Observe the chat response and citation badges at the bottom of the reply.
  3. Hover over and click the citation badges (`[1]`, `[2]`, etc.).
- **Expected Results**:
  - The response explains Leverage, Neutral, and Overhead tasks.
  - Perplexity-style citation pills display the speaker name (e.g. Shreyas Doshi), episode title, and timestamp.
  - Hovering/clicking expands the exact transcript quote excerpt.
  - Pass/Fail: Pass.

---

### Test Case 3: Flexible Model Switching
- **Objective**: Verify the live toggle between Local and Cloud execution engines.
- **Steps**:
  1. In the Left Sidebar under "Execution Engine", note the active mode (Default: Local).
  2. Click **Cloud**.
  3. Observe the model display changing to Cloud model (e.g., `gpt-4o-mini`).
  4. Send a follow-up query: *"Give me a 2-sentence summary of Marty Cagan's 4 product risks."*
  5. Click **Local**.
  6. Verify the toggle immediately updates without page reload.
- **Expected Results**:
  - Engine switcher updates visual state smoothly.
  - Queries are handled by the selected engine (or fallback if API keys / Ollama are absent).
  - Pass/Fail: Pass.

---

### Test Case 4: Ship 30 for 30 Content Skill
- **Objective**: Verify that the dedicated Ship 30 essay skill produces structured, skimmable essays.
- **Steps**:
  1. In the Left Sidebar or composer bar, click **Ship 30 Skill** (or `Ship 30 for 30 Essay`).
  2. Observe the generated response.
- **Expected Results**:
  - Assistant outputs a structured ~1,250-word masterclass essay.
  - Formatting adheres to Ship 30 principles: punchy 1-line hook, 4-part narrative arc, 1-2 sentence paragraphs, bold headers, and actionable takeaways.
  - Generates an artifact badge or linked artifact in the chat.
  - Pass/Fail: Pass.

---

### Test Case 5: Side-by-Side Artifact Viewer & Sandboxing
- **Objective**: Verify Claude-style artifact panel rendering and iframe sandbox security.
- **Steps**:
  1. Click the starter prompt: *"Generate an HTML dashboard mockup artifact for tracking activation metrics and PQLs."*
  2. Wait for the response. Observe the right-side Artifact Viewer expanding automatically.
  3. Click the **Preview** tab to see the live rendered HTML component.
  4. Click the **Code** tab to view the underlying HTML/CSS code snippet.
  5. Click the **Copy** icon button in the artifact header.
  6. Inspect iframe sandbox in DevTools (`F12`): verify `sandbox="allow-scripts"` and omission of `allow-same-origin`.
- **Expected Results**:
  - Split pane slides in smoothly on the right.
  - Live dashboard renders inside the sandboxed iframe without errors.
  - Code block displays formatted syntax.
  - Copy button confirms clipboard copy with feedback.
  - Sandboxing prevents unauthorized host window/DOM access.
  - Pass/Fail: Pass.

---

### Test Case 6: Session Lifecycle & Persistence
- **Objective**: Verify that sessions and messages persist across navigation and reload.
- **Steps**:
  1. Click **+ New Conversation** (or press `Ctrl+N`).
  2. Confirm a new empty session is opened with the welcome screen.
  3. Send a message: *"Who is Elena Verna?"*
  4. Verify the session title in the sidebar updates to a contextual name.
  5. Click on the previous session in the sidebar list.
  6. Refresh the browser page (`F5`).
- **Expected Results**:
  - Historical conversation and its messages are fully restored from SQLite.
  - Hovering a session displays the delete trash icon; clicking deletes the session and clears its messages.
  - Pass/Fail: Pass.
