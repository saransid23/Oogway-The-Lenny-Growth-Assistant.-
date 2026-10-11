import logging
from typing import Tuple, List, Dict, Any, Optional
from app.llm.provider import llm_provider
from app.skills.ship30 import ship30_skill
from app.skills.artifact_generator import artifact_generator
from app.models import Citation, ArtifactResponse
from app.rag.retriever import retriever

logger = logging.getLogger("lenny_assistant.agent_router")

class AgentRouter:
    """
    Lenny Growth Assistant Agentic Routing & Intent Classifier Layer
    Directs queries to appropriate skills, RAG retrieval, or artifact generators.
    """

    async def route_and_execute(
        self,
        session_id: str,
        user_message: str,
        chat_history: List[Dict[str, str]] = None,
        requested_provider: Optional[str] = None,
        requested_skill: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        
        logger.info(f"AgentRouter processing message for session {session_id}. Requested skill: {requested_skill}")

        # 1. Intent Classification
        msg_lower = user_message.lower()
        is_ship30 = requested_skill == "ship30" or "ship 30" in msg_lower or "growth essay" in msg_lower
        is_html_artifact = ("html" in msg_lower or "dashboard" in msg_lower or "mockup" in msg_lower) and "code" in msg_lower

        citations: List[Citation] = []
        reply_text = ""
        provider_used = requested_provider or "local"
        model_used = model_name or "mistral"

        # 2. Skill Dispatch
        if is_ship30:
            logger.info("Routing to Ship 30 for 30 Content Skill")
            reply_text, citations = await ship30_skill.generate_essay(topic=user_message)
            model_used = "ship30-skill"

        elif is_html_artifact and not any(k in msg_lower for k in ["what", "how", "why"]):
            logger.info("Routing to HTML Artifact Synthesizer")
            reply_text = self._generate_html_dashboard_artifact(user_message)
            _, citations = retriever.search(user_message, top_k=2)

        else:
            logger.info("Routing to Grounded RAG Assistant Conversation Engine")
            reply_text, provider_used, model_used, citations = await llm_provider.generate_response(
                query=user_message,
                chat_history=chat_history,
                requested_provider=requested_provider,
                model_name=model_name
            )

        # 3. Artifact Extraction
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
            "artifact_dict": artifact_dict
        }

    def _generate_html_dashboard_artifact(self, topic: str) -> str:
        return f"""Here is a custom, fully interactive HTML/CSS dashboard mockup artifact for **{topic}**:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, sans-serif; background: #09090b; color: #fafafa; padding: 24px; margin: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }}
    .card {{ background: #18181b; border: 1px solid #27272a; padding: 18px; border-radius: 10px; }}
    .card-val {{ font-size: 1.8rem; font-weight: 700; color: #f59e0b; margin-top: 6px; }}
    .label {{ font-size: 0.75rem; color: #a1a1aa; text-transform: uppercase; letter-spacing: 0.5px; }}
    .table-box {{ background: #18181b; border: 1px solid #27272a; border-radius: 10px; padding: 18px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #27272a; font-size: 0.85rem; }}
    th {{ color: #71717a; font-weight: 600; }}
    .badge {{ background: rgba(16,185,129,0.15); color: #10b981; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; }}
  </style>
</head>
<body>
  <h2 style="font-size: 1.2rem; margin-bottom: 16px;">Product-Led Growth Telemetry Dashboard</h2>
  <div class="grid">
    <div class="card">
      <div class="label">Product Qualified Leads (PQLs)</div>
      <div class="card-val">1,420</div>
    </div>
    <div class="card">
      <div class="label">48h Activation Rate</div>
      <div class="card-val">68.4%</div>
    </div>
    <div class="card">
      <div class="label">Viral Invites / User</div>
      <div class="card-val">2.8x</div>
    </div>
  </div>

  <div class="table-box">
    <strong style="font-size: 0.95rem;">Top Converting Usage Triggers (Elena Verna PLG Loop)</strong>
    <table>
      <thead>
        <tr><th>Trigger Event</th><th>Accounts Reached</th><th>Conversion Rate</th><th>Status</th></tr>
      </thead>
      <tbody>
        <tr><td>Created >2 Boards in 48h</td><td>480 accounts</td><td>34.2%</td><td><span class="badge">Active</span></td></tr>
        <tr><td>Invited Team Member</td><td>890 accounts</td><td>42.8%</td><td><span class="badge">High Growth</span></td></tr>
        <tr><td>Exported PDF Artifact</td><td>210 accounts</td><td>18.5%</td><td><span class="badge">Active</span></td></tr>
      </tbody>
    </table>
  </div>
</body>
</html>
```
"""

agent_router = AgentRouter()
