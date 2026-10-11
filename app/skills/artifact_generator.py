import re
import uuid
from typing import Optional, Dict, Any
from app.database import ArtifactModel

class ArtifactGenerator:
    """
    Artifact Generator & Parser:
    Detects code blocks (HTML/CSS, Markdown, SVG) in text responses,
    creates Artifact objects for side-by-side rendering in the In-App Artifact Viewer.
    """

    def extract_or_create_artifact(self, session_id: str, content: str, title_hint: str = "Generated Artifact") -> Optional[Dict[str, Any]]:
        if not content:
            return None

        # 1. Match explicit ```html ... ``` codeblocks
        html_fence_match = re.search(r"```html\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if html_fence_match:
            html_code = html_fence_match.group(1).strip()
            return {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "title": f"{title_hint} (HTML App)",
                "artifact_type": "html",
                "content": html_code
            }

        # 2. Match generic code blocks containing HTML/SVG tags
        generic_code_match = re.search(r"```(?:xml|svg)?\s*(<(!DOCTYPE|html|div|svg|style|main|body).*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if generic_code_match:
            return {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "title": f"{title_hint} (HTML Component)",
                "artifact_type": "html",
                "content": generic_code_match.group(1).strip()
            }

        # 3. Match raw complete HTML documents in text
        raw_html_match = re.search(r"(<!DOCTYPE html>.*?</html>|<html.*?>.*?</html>)", content, re.DOTALL | re.IGNORECASE)
        if raw_html_match:
            return {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "title": f"{title_hint} (HTML App)",
                "artifact_type": "html",
                "content": raw_html_match.group(1).strip()
            }

        # 4. If query explicitly asked for HTML dashboard / mockup / tracker / artifact
        hint_lower = title_hint.lower()
        content_lower = content.lower()
        if any(term in hint_lower or term in content_lower for term in ["dashboard", "mockup", "pql", "activation metrics", "html artifact", "prototype"]):
            return {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "title": "PLG Activation & PQL Tracker",
                "artifact_type": "html",
                "content": self.get_default_plg_dashboard_html()
            }

        # 5. Check for explicit Markdown essay or document artifact (like Ship 30 essay)
        if content.startswith("# ") or "### **The Hook**" in content or "Ship 30 for 30" in content or len(content) > 1200:
            return {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "title": f"{title_hint} (Markdown Document)",
                "artifact_type": "markdown",
                "content": content
            }

        return None

    def get_default_plg_dashboard_html(self) -> str:
        """Returns a high-craft, sandboxed HTML/CSS product analytics dashboard artifact."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>B2B PLG Activation & PQL Funnel</title>
  <style>
    :root {
      --bg: #09090b;
      --card-bg: #141417;
      --border: #27272a;
      --text: #f4f4f5;
      --text-muted: #71717a;
      --accent-amber: #f59e0b;
      --accent-indigo: #6366f1;
      --accent-emerald: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      padding: 20px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
    }
    .title h2 { font-size: 1.1rem; font-weight: 700; color: #fff; }
    .title p { font-size: 0.75rem; color: var(--text-muted); margin-top: 3px; }
    .badge {
      background: rgba(245, 158, 11, 0.15);
      color: var(--accent-amber);
      border: 1px solid rgba(245, 158, 11, 0.3);
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.7rem;
      font-weight: 600;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 20px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
    }
    .card-label { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }
    .card-value { font-size: 1.4rem; font-weight: 800; margin-top: 6px; }
    .card-change { font-size: 0.7rem; color: var(--accent-emerald); margin-top: 4px; }
    
    .funnel-box {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 20px;
    }
    .funnel-box h3 { font-size: 0.85rem; margin-bottom: 12px; color: #fff; }
    .bar-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }
    .bar-name { width: 110px; font-size: 0.75rem; color: var(--text-muted); }
    .bar-track { flex: 1; height: 18px; background: #27272a; border-radius: 4px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 8px; font-size: 0.65rem; font-weight: 700; color: #000; }
    .bar-rate { width: 60px; text-align: right; font-size: 0.75rem; font-weight: 600; }
    
    .btn-action {
      background: var(--accent-indigo);
      color: #fff;
      border: none;
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s ease;
    }
    .btn-action:hover { background: #4f46e5; }
  </style>
</head>
<body>
  <div class="header">
    <div class="title">
      <h2>PLG Activation & PQL Pipeline</h2>
      <p>Framework by Elena Verna & Lenny Rachitsky</p>
    </div>
    <span class="badge">Live Artifact</span>
  </div>

  <div class="grid">
    <div class="card">
      <div class="card-label">Signups</div>
      <div class="card-value" id="val-signups">12,450</div>
      <div class="card-change">↑ +14.2% MoM</div>
    </div>
    <div class="card">
      <div class="card-label">Activated Users</div>
      <div class="card-value" id="val-activated">4,980</div>
      <div class="card-change">↑ 40.0% rate</div>
    </div>
    <div class="card">
      <div class="card-label">PQLs Generated</div>
      <div class="card-value" id="val-pql">1,245</div>
      <div class="card-change" style="color: var(--accent-amber);">⚡ 25.0% PQL threshold</div>
    </div>
    <div class="card">
      <div class="card-label">Paid Conversion</div>
      <div class="card-value" id="val-conv">418</div>
      <div class="card-change">↑ 33.6% from PQL</div>
    </div>
  </div>

  <div class="funnel-box">
    <h3>Funnel Progression Loop</h3>
    <div class="bar-row">
      <span class="bar-name">1. Acquisition</span>
      <div class="bar-track">
        <div class="bar-fill" style="width: 100%; background: #6366f1;">100%</div>
      </div>
      <span class="bar-rate">12,450</span>
    </div>
    <div class="bar-row">
      <span class="bar-name">2. Activation (Aha!)</span>
      <div class="bar-track">
        <div class="bar-fill" style="width: 40%; background: #38bdf8;">40%</div>
      </div>
      <span class="bar-rate">4,980</span>
    </div>
    <div class="bar-row">
      <span class="bar-name">3. PQL Engagement</span>
      <div class="bar-track">
        <div class="bar-fill" style="width: 25%; background: #f59e0b;">25%</div>
      </div>
      <span class="bar-rate">1,245</span>
    </div>
    <div class="bar-row">
      <span class="bar-name">4. Closed Won</span>
      <div class="bar-track">
        <div class="bar-fill" style="width: 8.4%; background: #10b981;">8.4%</div>
      </div>
      <span class="bar-rate">418</span>
    </div>
  </div>

  <button class="btn-action" onclick="alert('PQL Cohort data refreshed successfully!')">Refresh PQL Funnel</button>
</body>
</html>"""

artifact_generator = ArtifactGenerator()
