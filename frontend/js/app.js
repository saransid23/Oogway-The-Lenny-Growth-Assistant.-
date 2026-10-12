/* -------------------------------------------------------------
   LENNY'S GROWTH ASSISTANT — HUMAN-CRAFTED FRONTEND LOGIC
   ------------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentSessionId = localStorage.getItem("lenny_session_id") || null;
  let activeProvider = "local"; // 'local' or 'cloud'
  let activeArtifact = null;

  // DOM Elements
  const btnNewChat = document.getElementById("btn-new-chat");
  const sessionsList = document.getElementById("sessions-list");
  const messagesContainer = document.getElementById("messages-container");
  const welcomeHero = document.getElementById("welcome-hero");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatTitle = document.getElementById("chat-title");
  
  const btnProviderLocal = document.getElementById("btn-provider-local");
  const btnProviderCloud = document.getElementById("btn-provider-cloud");
  const activeModelDisplay = document.getElementById("active-model-display");
  const ollamaStatusBadge = document.getElementById("ollama-status-badge");
  
  const btnSkillShip30 = document.getElementById("btn-skill-ship30");
  const btnQuickSkill = document.getElementById("btn-quick-skill");
  const promptCards = document.querySelectorAll(".prompt-card");
  
  const artifactPane = document.getElementById("artifact-pane");
  const btnToggleArtifact = document.getElementById("btn-toggle-artifact-pane");
  const btnCloseArtifact = document.getElementById("btn-close-artifact");
  const artifactTitle = document.getElementById("artifact-title");
  const artifactSubTag = document.getElementById("artifact-sub-tag");
  const artifactCountBadge = document.getElementById("artifact-count-badge");
  const tabRender = document.getElementById("tab-render");
  const tabCode = document.getElementById("tab-code");
  const renderView = document.getElementById("artifact-render-view");
  const codeView = document.getElementById("artifact-code-view");
  const artifactIframe = document.getElementById("artifact-iframe");
  const artifactMarkdownView = document.getElementById("artifact-markdown-view");
  const artifactCodeBlock = document.getElementById("artifact-code-block");
  const btnCopyArtifact = document.getElementById("btn-copy-artifact");
  
  const btnToggleSidebar = document.getElementById("btn-toggle-sidebar");
  const sidebar = document.getElementById("sidebar");

  // -------------------------------------------------------------
  // INIT
  // -------------------------------------------------------------
  init();

  async function init() {
    await checkHealth();
    await loadSessions();
    
    if (currentSessionId) {
      await loadSessionMessages(currentSessionId);
    }

    setupEventListeners();
  }

  async function checkHealth() {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const data = await res.json();
        const kbCountElem = document.getElementById("kb-transcript-count");
        if (kbCountElem) {
          kbCountElem.innerText = `RAG: ${data.transcripts_loaded} Transcript Chunks`;
        }

        if (data.ollama_status.includes("online")) {
          ollamaStatusBadge.innerText = "Ollama";
          ollamaStatusBadge.className = "status-badge online";
        } else {
          ollamaStatusBadge.innerText = "RAG Engine";
          ollamaStatusBadge.className = "status-badge online";
          ollamaStatusBadge.style.background = "rgba(245, 158, 11, 0.15)";
          ollamaStatusBadge.style.color = "#F59E0B";
        }
      }
    } catch (err) {
      console.warn("Health check error:", err);
    }
  }

  // -------------------------------------------------------------
  // SESSIONS
  // -------------------------------------------------------------
  async function loadSessions() {
    try {
      const res = await fetch("/api/sessions");
      if (res.ok) {
        const sessions = await res.json();
        renderSessionsList(sessions);
      }
    } catch (err) {
      console.error("Error loading sessions:", err);
    }
  }

  function renderSessionsList(sessions) {
    sessionsList.innerHTML = "";
    if (sessions.length === 0) {
      sessionsList.innerHTML = `<div class="history-item">No saved chats</div>`;
      return;
    }

    sessions.forEach((s) => {
      const item = document.createElement("div");
      item.className = `history-item ${s.id === currentSessionId ? "active" : ""}`;
      item.innerHTML = `
        <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"><i class="fa-regular fa-message" style="margin-right:6px;"></i> ${escapeHtml(s.title)}</span>
        <i class="fa-solid fa-trash btn-delete-session" data-id="${s.id}" style="font-size:0.7rem; opacity:0.4;"></i>
      `;
      
      item.addEventListener("click", (e) => {
        if (e.target.classList.contains("btn-delete-session")) {
          e.stopPropagation();
          deleteSession(s.id);
        } else {
          switchSession(s.id);
        }
      });

      sessionsList.appendChild(item);
    });
  }

  async function createNewSession(title = "New Growth Conversation") {
    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, provider: activeProvider })
      });
      if (res.ok) {
        const s = await res.json();
        currentSessionId = s.id;
        localStorage.setItem("lenny_session_id", currentSessionId);
        messagesContainer.innerHTML = "";
        messagesContainer.appendChild(welcomeHero);
        welcomeHero.classList.remove("hidden");
        chatTitle.innerText = s.title;
        await loadSessions();
      }
    } catch (err) {
      console.error("Error creating session:", err);
    }
  }

  async function switchSession(sessionId) {
    currentSessionId = sessionId;
    localStorage.setItem("lenny_session_id", currentSessionId);
    await loadSessions();
    await loadSessionMessages(sessionId);
  }

  async function deleteSession(sessionId) {
    try {
      await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
      if (currentSessionId === sessionId) {
        currentSessionId = null;
        localStorage.removeItem("lenny_session_id");
        messagesContainer.innerHTML = "";
        messagesContainer.appendChild(welcomeHero);
        welcomeHero.classList.remove("hidden");
        chatTitle.innerText = "New Growth Conversation";
      }
      await loadSessions();
    } catch (err) {
      console.error("Error deleting session:", err);
    }
  }

  async function loadSessionMessages(sessionId) {
    try {
      const res = await fetch(`/api/sessions/${sessionId}/messages`);
      if (res.ok) {
        const msgs = await res.json();
        messagesContainer.innerHTML = "";
        if (msgs.length === 0) {
          messagesContainer.appendChild(welcomeHero);
          welcomeHero.classList.remove("hidden");
          activeArtifact = null;
          if (artifactCountBadge) artifactCountBadge.classList.add("hidden");
        } else {
          welcomeHero.classList.add("hidden");
          msgs.forEach((m) => appendMessageUI(m));

          // Auto-load and display the latest artifact in the session
          const lastArtifactMsg = msgs.slice().reverse().find((m) => m.artifact);
          if (lastArtifactMsg && lastArtifactMsg.artifact) {
            displayArtifact(lastArtifactMsg.artifact);
            if (artifactCountBadge) {
              artifactCountBadge.classList.remove("hidden");
              artifactCountBadge.innerText = "1";
            }
          } else {
            activeArtifact = null;
            if (artifactCountBadge) artifactCountBadge.classList.add("hidden");
          }

          scrollToBottom();
        }
      }
    } catch (err) {
      console.error("Error loading messages:", err);
    }
  }

  // -------------------------------------------------------------
  // MESSAGES & CHAT INTERACTION
  // -------------------------------------------------------------
  async function sendMessage(text, useSkill = null) {
    if (!text.trim()) return;

    if (!currentSessionId) {
      await createNewSession(text.substring(0, 30));
    }

    welcomeHero.classList.add("hidden");

    // Append User Message
    appendMessageUI({
      sender: "user",
      content: text
    });

    chatInput.value = "";
    chatInput.style.height = "auto";
    scrollToBottom();

    // Show Loading state
    const loadingElem = appendLoadingUI();
    scrollToBottom();

    // If Ship 30 skill explicitly requested, call skill endpoint
    if (useSkill === "ship30") {
      try {
        const res = await fetch("/api/skills/ship30", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: currentSessionId,
            topic: text,
            provider: activeProvider
          })
        });
        loadingElem.remove();
        if (res.ok) {
          const data = await res.json();
          appendMessageUI({
            sender: "assistant",
            content: data.reply,
            citations: data.citations,
            artifact: data.artifact
          });
          if (data.artifact) {
            displayArtifact(data.artifact);
            if (artifactCountBadge) artifactCountBadge.classList.remove("hidden");
          }
          await loadSessions();
          scrollToBottom();
        } else {
          appendMessageUI({
            sender: "assistant",
            content: "❌ Error connecting to Ship 30 Skill API."
          });
        }
      } catch (err) {
        loadingElem.remove();
        appendMessageUI({
          sender: "assistant",
          content: `❌ Communication Failure: ${err.message}`
        });
      }
      return;
    }

    // Standard Chat with SSE Streaming
    let streamStarted = false;
    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionId,
          message: text,
          provider: activeProvider,
          use_skill: useSkill
        })
      });

      if (!res.ok || !res.body) {
        throw new Error("Stream connection failed to initialize");
      }

      // Stream successfully initialized
      streamStarted = true;
      loadingElem.remove();

      // Create live assistant message row
      const liveRow = appendMessageUI({
        sender: "assistant",
        content: ""
      });
      const liveContentEl = liveRow.querySelector(".msg-content");
      if (liveContentEl) {
        liveContentEl.innerHTML = '<span style="color: var(--text-tertiary);"><i class="fa-solid fa-spinner fa-spin" style="margin-right:6px;"></i> Grounding answer & artifacts from transcripts...</span>';
      }
      let accumulatedText = "";
      let rafId = null;

      function scheduleRender() {
        if (rafId) return;
        rafId = requestAnimationFrame(() => {
          if (liveContentEl) {
            liveContentEl.innerHTML = formatMarkdownSafe(accumulatedText);
            scrollToBottom();
          }
          rafId = null;
        });
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const block of parts) {
          if (!block.trim()) continue;
          const lines = block.split("\n");
          let eventType = "message";
          let eventData = "";

          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.substring(6).trim();
            } else if (line.startsWith("data:")) {
              eventData = line.substring(5).trim();
            }
          }

          if (eventType === "token") {
            try {
              const parsed = JSON.parse(eventData);
              accumulatedText += (parsed.token || "");
              scheduleRender();
            } catch (e) {
              accumulatedText += eventData;
              scheduleRender();
            }
          } else if (eventType === "done") {
            if (rafId) {
              cancelAnimationFrame(rafId);
              rafId = null;
            }
            try {
              const finalData = JSON.parse(eventData);
              // Replace live row with fully formatted row including citations & artifacts
              liveRow.remove();
              appendMessageUI({
                sender: "assistant",
                content: finalData.reply || accumulatedText,
                citations: finalData.citations,
                artifact: finalData.artifact
              });

              if (finalData.artifact) {
                displayArtifact(finalData.artifact);
                if (artifactCountBadge) artifactCountBadge.classList.remove("hidden");
              }
            } catch (e) {
              if (liveContentEl) {
                liveContentEl.innerHTML = formatMarkdownSafe(accumulatedText);
              }
            }
            await loadSessions();
            scrollToBottom();
          } else if (eventType === "error") {
            let errMsg = "Stream error occurred";
            try {
              errMsg = JSON.parse(eventData).detail || errMsg;
            } catch (e) {}
            if (liveContentEl) {
              liveContentEl.innerHTML = formatMarkdownSafe(accumulatedText + `\n\n❌ *${errMsg}*`);
            }
          }
        }
      }

    } catch (streamErr) {
      if (streamStarted) {
        // Failed after starting: show error, DO NOT retry (user message was already stored on server)
        console.error("Stream aborted during read:", streamErr);
        appendMessageUI({
          sender: "assistant",
          content: `❌ Stream interrupted: ${streamErr.message}`
        });
      } else {
        // Fallback to /api/chat ONLY if stream never started
        console.warn("Stream could not start, falling back to /api/chat:", streamErr);
        try {
          const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: currentSessionId,
              message: text,
              provider: activeProvider,
              use_skill: useSkill
            })
          });
          loadingElem.remove();
          if (res.ok) {
            const data = await res.json();
            appendMessageUI({
              sender: "assistant",
              content: data.reply,
              citations: data.citations,
              artifact: data.artifact
            });
            if (data.artifact) {
              displayArtifact(data.artifact);
              if (artifactCountBadge) artifactCountBadge.classList.remove("hidden");
            }
            await loadSessions();
            scrollToBottom();
          } else {
            appendMessageUI({
              sender: "assistant",
              content: "❌ Error connecting to Assistant API."
            });
          }
        } catch (fallbackErr) {
          loadingElem.remove();
          appendMessageUI({
            sender: "assistant",
            content: `❌ Communication Failure: ${fallbackErr.message}`
          });
        }
      }
    }
  }

  function formatMarkdownSafe(text) {
    if (!text) return "";
    if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
      try {
        return DOMPurify.sanitize(marked.parse(text));
      } catch (e) {
        return escapeHtml(text);
      }
    } else if (typeof marked !== "undefined") {
      try {
        return marked.parse(text);
      } catch (e) {
        return escapeHtml(text);
      }
    }
    return escapeHtml(text);
  }

  function appendMessageUI(msg) {
    const row = document.createElement("div");
    row.className = `msg-row ${msg.sender}`;

    const avatar = msg.sender === "user" ? "YOU" : "LG";
    const authorName = msg.sender === "user" ? "You" : "Lenny Growth Assistant";

    // Perplexity style citations
    let citationsHtml = "";
    if (msg.citations && msg.citations.length > 0) {
      citationsHtml = `<div class="citations-container">`;
      msg.citations.forEach((c) => {
        citationsHtml += `
          <div class="citation-badge" title="${escapeHtml(c.quote || '')}">
            <i class="fa-solid fa-quote-left"></i> ${escapeHtml(c.guest || 'Guest')} • ${escapeHtml(c.timestamp || '')}
          </div>
        `;
      });
      citationsHtml += `</div>`;
    }

    // Claude style embedded artifact card
    let artifactCardHtml = "";
    if (msg.artifact) {
      artifactCardHtml = `
        <div class="artifact-embedded-card" data-artifact-id="${msg.artifact.id}">
          <div class="card-title-group">
            <i class="fa-solid fa-file-code"></i>
            <div>
              <strong>${escapeHtml(msg.artifact.title)}</strong>
              <span>Click to view rendered output & source code</span>
            </div>
          </div>
          <i class="fa-solid fa-chevron-right" style="color: var(--text-tertiary); font-size:0.8rem;"></i>
        </div>
      `;
    }

    const formattedBody = formatMarkdownSafe(msg.content || "");

    row.innerHTML = `
      <div class="msg-avatar">${avatar}</div>
      <div class="msg-body-box">
        <span class="msg-author">${authorName}</span>
        <div class="msg-content">${formattedBody}</div>
        ${citationsHtml}
        ${artifactCardHtml}
      </div>
    `;

    if (msg.artifact) {
      const card = row.querySelector(".artifact-embedded-card");
      if (card) {
        card.addEventListener("click", () => displayArtifact(msg.artifact));
      }
    }

    messagesContainer.appendChild(row);
    return row;
  }

  function appendLoadingUI() {
    const row = document.createElement("div");
    row.className = "msg-row assistant";
    row.innerHTML = `
      <div class="msg-avatar">LG</div>
      <div class="msg-body-box">
        <span class="msg-author">Lenny Growth Assistant</span>
        <div class="msg-content" style="color: var(--text-tertiary);">
          <i class="fa-solid fa-spinner fa-spin"></i> Grounding answer from Lenny's Podcast transcripts...
        </div>
      </div>
    `;
    messagesContainer.appendChild(row);
    return row;
  }

  function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // -------------------------------------------------------------
  // ARTIFACT VIEWER
  // -------------------------------------------------------------
  function displayArtifact(artifact) {
    if (!artifact) return;
    activeArtifact = artifact;
    artifactTitle.innerText = artifact.title || "Generated Artifact";
    artifactSubTag.innerText = artifact.artifact_type === "html" ? "HTML Render Snippet" : "Markdown Document";

    if (artifact.artifact_type === "html") {
      artifactIframe.classList.remove("hidden");
      artifactMarkdownView.classList.add("hidden");
      
      // Use srcdoc for secure sandboxed iframe rendering (prevents cross-origin DOM exceptions)
      artifactIframe.srcdoc = artifact.content;
    } else {
      artifactIframe.classList.add("hidden");
      artifactMarkdownView.classList.remove("hidden");
      
      if (typeof marked !== "undefined") {
        const rawHtml = marked.parse(artifact.content);
        artifactMarkdownView.innerHTML = (typeof DOMPurify !== "undefined") ? DOMPurify.sanitize(rawHtml) : rawHtml;
      } else {
        artifactMarkdownView.innerText = artifact.content;
      }
    }

    artifactCodeBlock.textContent = artifact.content;
    switchArtifactTab("render");
    artifactPane.classList.remove("collapsed");
    if (artifactCountBadge) {
      artifactCountBadge.classList.remove("hidden");
      artifactCountBadge.innerText = "1";
    }
  }

  function switchArtifactTab(tab) {
    if (tab === "render") {
      tabRender.classList.add("active");
      tabCode.classList.remove("active");
      renderView.classList.add("active");
      renderView.classList.remove("hidden");
      codeView.classList.remove("active");
      codeView.classList.add("hidden");
    } else {
      tabCode.classList.add("active");
      tabRender.classList.remove("active");
      codeView.classList.add("active");
      codeView.classList.remove("hidden");
      renderView.classList.remove("active");
      renderView.classList.add("hidden");
    }
  }

  function getDefaultDemoDashboard() {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { background: #09090b; color: #f4f4f5; font-family: sans-serif; padding: 20px; }
    h2 { font-size: 1.1rem; color: #fff; margin-bottom: 4px; }
    p { font-size: 0.75rem; color: #71717a; margin-bottom: 16px; }
    .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 16px; }
    .card { background: #141417; border: 1px solid #27272a; padding: 12px; border-radius: 8px; }
    .label { font-size: 0.7rem; color: #71717a; text-transform: uppercase; font-weight: bold; }
    .val { font-size: 1.3rem; font-weight: 800; margin-top: 4px; color: #f59e0b; }
    .bar-box { background: #141417; border: 1px solid #27272a; padding: 14px; border-radius: 8px; }
    .bar { height: 16px; background: #27272a; border-radius: 4px; overflow: hidden; margin: 8px 0; }
    .fill { height: 100%; background: #6366f1; border-radius: 4px; }
  </style>
</head>
<body>
  <h2>B2B PLG Activation Tracker</h2>
  <p>Elena Verna Growth & PQL Framework</p>
  <div class="grid">
    <div class="card"><div class="label">Total Signups</div><div class="val">14,200</div></div>
    <div class="card"><div class="label">PQLs Identified</div><div class="val">1,420</div></div>
    <div class="card"><div class="label">Activation Rate</div><div class="val" style="color:#10b981;">38.5%</div></div>
    <div class="card"><div class="label">Paid Win Rate</div><div class="val" style="color:#38bdf8;">32.0%</div></div>
  </div>
  <div class="bar-box">
    <div style="font-size:0.75rem; font-weight:bold;">Activation Milestone Funnel</div>
    <div class="bar"><div class="fill" style="width: 38.5%;"></div></div>
    <div style="font-size:0.7rem; color:#71717a;">38.5% reach Core Aha Moment within 48h</div>
  </div>
</body>
</html>`;
  }

  // -------------------------------------------------------------
  // EVENT LISTENERS & SHORTCUTS
  // -------------------------------------------------------------
  function setupEventListeners() {
    btnNewChat.addEventListener("click", () => createNewSession());

    // Keyboard shortcut: Ctrl+N or Cmd+N for New Chat
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        createNewSession();
      }
    });

    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      sendMessage(chatInput.value);
    });

    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event("submit"));
      }
    });

    btnProviderLocal.addEventListener("click", () => {
      activeProvider = "local";
      btnProviderLocal.classList.add("active");
      btnProviderCloud.classList.remove("active");
      activeModelDisplay.innerText = "Model: mistral (7B)";
    });

    btnProviderCloud.addEventListener("click", () => {
      activeProvider = "cloud";
      btnProviderCloud.classList.add("active");
      btnProviderLocal.classList.remove("active");
      activeModelDisplay.innerText = "Model: gpt-4o-mini";
    });

    const triggerSkillFn = () => {
      const topic = prompt("Enter topic for Ship 30 for 30 Growth Essay:", "Product-Led Growth & Activation Metrics");
      if (topic) {
        sendMessage(topic, "ship30");
      }
    };

    if (btnSkillShip30) btnSkillShip30.addEventListener("click", triggerSkillFn);
    if (btnQuickSkill) btnQuickSkill.addEventListener("click", triggerSkillFn);

    promptCards.forEach((card) => {
      card.addEventListener("click", () => {
        const promptText = card.getAttribute("data-prompt");
        chatInput.value = promptText;
        chatForm.dispatchEvent(new Event("submit"));
      });
    });

    btnToggleArtifact.addEventListener("click", () => {
      if (artifactPane.classList.contains("collapsed")) {
        if (!activeArtifact) {
          const cards = document.querySelectorAll(".artifact-embedded-card");
          if (cards.length > 0) {
            cards[cards.length - 1].click();
            return;
          }
          displayArtifact({
            id: "default-dashboard",
            session_id: currentSessionId || "default",
            title: "PLG Activation & PQL Tracker",
            artifact_type: "html",
            content: getDefaultDemoDashboard()
          });
        } else {
          displayArtifact(activeArtifact);
        }
        artifactPane.classList.remove("collapsed");
      } else {
        artifactPane.classList.add("collapsed");
      }
    });

    btnCloseArtifact.addEventListener("click", () => {
      artifactPane.classList.add("collapsed");
    });

    tabRender.addEventListener("click", () => switchArtifactTab("render"));
    tabCode.addEventListener("click", () => switchArtifactTab("code"));

    btnCopyArtifact.addEventListener("click", () => {
      if (activeArtifact && activeArtifact.content) {
        navigator.clipboard.writeText(activeArtifact.content);
        alert("Artifact code copied to clipboard!");
      }
    });

    if (btnToggleSidebar) {
      btnToggleSidebar.addEventListener("click", () => {
        sidebar.classList.toggle("open");
      });
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
});
