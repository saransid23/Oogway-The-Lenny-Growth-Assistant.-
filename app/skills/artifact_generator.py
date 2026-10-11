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
        # 1. Check for HTML codeblock
        html_match = re.search(r"```html\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_code = html_match.group(1).strip()
            return {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "title": f"{title_hint} (HTML App)",
                "artifact_type": "html",
                "content": html_code
            }

        # 2. Check for explicit Markdown essay or document artifact (like Ship 30 essay)
        if content.startswith("# ") or "### **The Hook**" in content or len(content) > 1500:
            return {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "title": f"{title_hint} (Markdown Document)",
                "artifact_type": "markdown",
                "content": content
            }

        return None

artifact_generator = ArtifactGenerator()
