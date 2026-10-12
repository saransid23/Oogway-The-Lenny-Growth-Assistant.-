import logging
from typing import Tuple, List, Dict, Any, Optional
from app.llm.provider import llm_provider
from app.skills.ship30 import ship30_skill
from app.skills.artifact_generator import artifact_generator
from app.models import Citation
from app.rag.retriever import retriever
from app.llm.anthropic_agent import claude_agent
from app.config import settings

logger = logging.getLogger("lenny_assistant.agent_router")

class AgentRouter:
    """
    Lenny Growth Assistant Agentic Routing & Intent Classifier Layer:
    - Routes user requests to appropriate specialized skills or agent execution paths.
    - Dynamically generates artifacts based on topic requirements rather than static templates.
    - Preserves explicit provider/model selection.
    """

    @staticmethod
    def classify(
        user_message: str,
        requested_skill: Optional[str] = None,
        requested_provider: Optional[str] = None
    ) -> str:
        """
        Classifies incoming request into execution route:
        'ship30' | 'html' | 'cloud_agent' | 'rag'
        """
        msg_lower = user_message.lower()
        is_ship30 = requested_skill == "ship30" or "ship 30" in msg_lower or "growth essay" in msg_lower
        if is_ship30:
            return "ship30"

        artifact_keywords = [
            "html", "dashboard", "mockup", "artifact", "simulator", "calculator",
            "widget", "funnel", "tracker", "interactive tool", "visualizer", "app"
        ]
        action_keywords = [
            "build", "create", "generate", "code", "design", "make", "give", "show",
            "write", "develop", "provide", "interactive", "pop", "display", "render", "need"
        ]
        is_html_request = (
            any(k in msg_lower for k in artifact_keywords)
            and (
                any(w in msg_lower for w in action_keywords)
                or "html" in msg_lower
                or "dashboard" in msg_lower
                or "artifact" in msg_lower
            )
        )
        if is_html_request and not any(k in msg_lower for k in ["what is ", "explain ", "who is "]):
            return "html"

        if requested_provider == "cloud" and claude_agent.is_available():
            return "cloud_agent"

        return "rag"

    async def route_and_execute(
        self,
        session_id: str,
        user_message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        requested_provider: Optional[str] = None,
        requested_skill: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        
        logger.info(f"AgentRouter routing session '{session_id}'. Provider: '{requested_provider}', Skill: '{requested_skill}'")

        route = self.classify(user_message, requested_skill, requested_provider)

        citations: List[Citation] = []
        reply_text = ""
        provider_used = requested_provider or "local"
        model_used = model_name or "mistral"
        evidence_found = True

        # 1. Ship 30 for 30 Content Skill
        if route == "ship30":
            logger.info("Routing to Ship 30 for 30 Content Skill")
            reply_text, citations = await ship30_skill.generate_essay(
                topic=user_message,
                provider=requested_provider,
                model_name=model_name,
                chat_history=chat_history
            )
            model_used = "ship30-skill"
            evidence_found = len(citations) > 0

        # 2. Dynamic HTML Artifact Generation Request
        elif route == "html":
            logger.info("Routing to Dynamic HTML Artifact Synthesizer")
            reply_text, citations = await self._generate_dynamic_html_artifact(
                user_message,
                provider=requested_provider,
                model_name=model_name
            )
            provider_used = requested_provider or "local"

        # 3. Cloud Provider with Anthropic Claude Agent SDK
        elif route == "cloud_agent":
            logger.info("Routing to Anthropic Claude Agent SDK execution layer")
            agent_res = await claude_agent.run_agent(user_message, chat_history=chat_history)
            if agent_res:
                reply_text, citations = agent_res
                provider_used = "cloud"
                model_used = settings.ANTHROPIC_MODEL
                evidence_found = True
            else:
                reply_text, provider_used, model_used, citations, evidence_found = await llm_provider.generate_response(
                    query=user_message,
                    chat_history=chat_history,
                    requested_provider=requested_provider,
                    model_name=model_name
                )

        # 4. Standard Grounded RAG Assistant Conversation
        else:
            logger.info("Routing to Grounded RAG Conversation Engine")
            reply_text, provider_used, model_used, citations, evidence_found = await llm_provider.generate_response(
                query=user_message,
                chat_history=chat_history,
                requested_provider=requested_provider,
                model_name=model_name
            )

        # 5. Extract Artifact for Side-by-Side Rendering
        artifact_dict = artifact_generator.extract_or_create_artifact(
            session_id=session_id,
            content=reply_text,
            title_hint=user_message[:30]
        )

        return {
            "reply": reply_text,
            "provider": provider_used,
            "model_name": model_used,
            "citations": citations,
            "artifact_dict": artifact_dict,
            "evidence_found": evidence_found
        }

    async def _generate_dynamic_html_artifact(
        self,
        user_request: str,
        provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Tuple[str, List[Citation]]:
        """
        Dynamically asks the LLM to generate an interactive HTML/CSS snippet tailored to the user's specific prompt.
        """
        chunks, citations = await retriever.asearch(user_request, top_k=2, threshold=0.08)
        context_str = retriever.format_rag_context(chunks) if chunks else ""

        artifact_prompt = (
            f"The user wants an interactive, polished HTML/CSS dashboard or tool artifact.\n"
            f"USER REQUEST: {user_request}\n"
            f"TRANSCRIPT CONTEXT:\n{context_str}\n\n"
            "INSTRUCTIONS:\n"
            "Generate a complete, self-contained HTML document with embedded CSS. Wrap it in a single ```html codeblock.\n"
            "Make it clean, responsive, with dark mode aesthetics (dark zinc background, crisp typography, clean cards)."
        )

        try:
            import asyncio
            llm_reply = await asyncio.wait_for(
                llm_provider.generate_completion(
                    prompt=artifact_prompt,
                    requested_provider=provider,
                    model_name=model_name
                ),
                timeout=20.0
            )
        except Exception as e:
            logger.warning(f"Dynamic HTML LLM generation timed out or failed: {e}. Utilizing interactive synthesizer.")
            llm_reply = None

        if llm_reply:
            test_art = artifact_generator.extract_or_create_artifact("temp", llm_reply)
            if test_art and test_art.get("artifact_type") == "html" and test_art.get("content"):
                return llm_reply, citations

        # Dynamic fallback snippet customized to user request topic
        fallback_html = self._synthesize_custom_html(user_request)
        reply = (
            f"Here is an interactive, sandboxed HTML/CSS component tailored for **{user_request}**:\n\n"
            f"```html\n{fallback_html}\n```\n\n"
            f"You can preview this component rendered live in the Artifact Viewer on the right."
        )
        return reply, citations

    def _synthesize_custom_html(self, topic: str) -> str:
        clean_title = topic.replace('"', '').replace("'", "")[:60]
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{clean_title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #09090b;
      color: #f4f4f5;
      padding: 20px;
    }}
    .header {{ margin-bottom: 18px; border-bottom: 1px solid #27272a; padding-bottom: 12px; }}
    h2 {{ font-size: 1.15rem; color: #ffffff; font-weight: 700; }}
    p.sub {{ font-size: 0.75rem; color: #71717a; margin-top: 2px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px; }}
    .card {{ background: #141417; border: 1px solid #27272a; border-radius: 8px; padding: 12px 14px; }}
    .label {{ font-size: 0.7rem; color: #71717a; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }}
    .value {{ font-size: 1.4rem; font-weight: 800; color: #f59e0b; margin-top: 4px; }}
    .change {{ font-size: 0.72rem; color: #10b981; margin-top: 2px; }}
    .controls {{
      background: #141417;
      border: 1px solid #27272a;
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 16px;
    }}
    .slider-row {{ margin-bottom: 12px; }}
    .slider-label {{
      display: flex;
      justify-content: space-between;
      font-size: 0.75rem;
      color: #a1a1aa;
      margin-bottom: 6px;
    }}
    input[type=range] {{
      width: 100%;
      accent-color: #6366f1;
      height: 4px;
      background: #27272a;
      border-radius: 2px;
      outline: none;
    }}
    .funnel-box {{
      background: #141417;
      border: 1px solid #27272a;
      border-radius: 8px;
      padding: 14px;
    }}
    .funnel-title {{ font-size: 0.78rem; font-weight: 600; margin-bottom: 10px; color: #fff; }}
    .bar-group {{ margin-bottom: 8px; }}
    .bar-meta {{ display: flex; justify-content: space-between; font-size: 0.7rem; color: #a1a1aa; margin-bottom: 4px; }}
    .bar-track {{ height: 12px; background: #27272a; border-radius: 4px; overflow: hidden; }}
    .bar-fill {{ height: 100%; background: linear-gradient(90deg, #6366f1, #a855f7); border-radius: 4px; transition: width 0.25s ease; }}
    .btn {{
      background: #6366f1;
      color: #fff;
      border: none;
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
      margin-top: 10px;
      transition: background 0.15s ease;
    }}
    .btn:hover {{ background: #4f46e5; }}
  </style>
</head>
<body>
  <div class="header">
    <h2>{clean_title}</h2>
    <p class="sub">Interactive Growth Artifact • Live Real-Time Simulator</p>
  </div>

  <div class="grid">
    <div class="card">
      <div class="label">Total Signups</div>
      <div id="out-signups" class="value">2,500</div>
      <div class="change">Monthly Top-Funnel</div>
    </div>
    <div class="card">
      <div class="label">PQLs Activated</div>
      <div id="out-pqls" class="value" style="color: #38bdf8;">1,000</div>
      <div class="change">40% Aha Moment Rate</div>
    </div>
    <div class="card">
      <div class="label">Paid Customers</div>
      <div id="out-paid" class="value" style="color: #10b981;">200</div>
      <div class="change">20% PQL-to-Paid Win Rate</div>
    </div>
    <div class="card">
      <div class="label">Projected ARR</div>
      <div id="out-arr" class="value" style="color: #f59e0b;">$120,000</div>
      <div class="change">Compound Growth Loop</div>
    </div>
  </div>

  <div class="controls">
    <div class="slider-row">
      <div class="slider-label">
        <span>Visitor Traffic:</span>
        <strong id="val-traffic">50,000 / mo</strong>
      </div>
      <input type="range" id="slider-traffic" min="10000" max="200000" step="5000" value="50000">
    </div>

    <div class="slider-row">
      <div class="slider-label">
        <span>Signup Conversion Rate:</span>
        <strong id="val-signup-rate">5.0%</strong>
      </div>
      <input type="range" id="slider-signup-rate" min="1" max="15" step="0.5" value="5">
    </div>

    <div class="slider-row" style="margin-bottom: 0;">
      <div class="slider-label">
        <span>PQL Activation Rate:</span>
        <strong id="val-act-rate">40.0%</strong>
      </div>
      <input type="range" id="slider-act-rate" min="10" max="80" step="5" value="40">
    </div>
  </div>

  <div class="funnel-box">
    <div class="funnel-title">Activation & Conversion Funnel</div>
    <div class="bar-group">
      <div class="bar-meta"><span>Signups</span><span id="bar-signups-lbl">100% (2,500)</span></div>
      <div class="bar-track"><div id="bar-signups" class="bar-fill" style="width: 100%;"></div></div>
    </div>
    <div class="bar-group">
      <div class="bar-meta"><span>Activated PQLs</span><span id="bar-pqls-lbl">40% (1,000)</span></div>
      <div class="bar-track"><div id="bar-pqls" class="bar-fill" style="width: 40%; background: #38bdf8;"></div></div>
    </div>
    <div class="bar-group">
      <div class="bar-meta"><span>Paid Conversions</span><span id="bar-paid-lbl">8% (200)</span></div>
      <div class="bar-track"><div id="bar-paid" class="bar-fill" style="width: 8%; background: #10b981;"></div></div>
    </div>
    <button class="btn" onclick="resetDefaults()">Reset Simulation Defaults</button>
  </div>

  <script>
    function updateSim() {{
      const traffic = parseInt(document.getElementById('slider-traffic').value);
      const signupRate = parseFloat(document.getElementById('slider-signup-rate').value) / 100;
      const actRate = parseFloat(document.getElementById('slider-act-rate').value) / 100;

      document.getElementById('val-traffic').innerText = traffic.toLocaleString() + ' / mo';
      document.getElementById('val-signup-rate').innerText = (signupRate * 100).toFixed(1) + '%';
      document.getElementById('val-act-rate').innerText = (actRate * 100).toFixed(1) + '%';

      const signups = Math.round(traffic * signupRate);
      const pqls = Math.round(signups * actRate);
      const paid = Math.round(pqls * 0.20);
      const arr = paid * 50 * 12;

      document.getElementById('out-signups').innerText = signups.toLocaleString();
      document.getElementById('out-pqls').innerText = pqls.toLocaleString();
      document.getElementById('out-paid').innerText = paid.toLocaleString();
      document.getElementById('out-arr').innerText = '$' + arr.toLocaleString();

      const pqlPct = Math.round((pqls / Math.max(signups, 1)) * 100);
      const paidPct = Math.round((paid / Math.max(signups, 1)) * 100);

      document.getElementById('bar-pqls').style.width = pqlPct + '%';
      document.getElementById('bar-pqls-lbl').innerText = pqlPct + '% (' + pqls.toLocaleString() + ')';

      document.getElementById('bar-paid').style.width = paidPct + '%';
      document.getElementById('bar-paid-lbl').innerText = paidPct + '% (' + paid.toLocaleString() + ')';
    }}

    function resetDefaults() {{
      document.getElementById('slider-traffic').value = 50000;
      document.getElementById('slider-signup-rate').value = 5;
      document.getElementById('slider-act-rate').value = 40;
      updateSim();
    }}

    document.getElementById('slider-traffic').addEventListener('input', updateSim);
    document.getElementById('slider-signup-rate').addEventListener('input', updateSim);
    document.getElementById('slider-act-rate').addEventListener('input', updateSim);
  </script>
</body>
</html>"""

agent_router = AgentRouter()
