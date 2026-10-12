import re
import uuid
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("lenny_assistant.artifact_generator")

MAX_ARTIFACT_SIZE_BYTES = 500 * 1024  # 500 KB limit to prevent DoS

class ArtifactGenerator:
    """
    Dynamic Artifact Generator & Sanitization Engine:
    - Extracts or dynamically synthesizes HTML/CSS and Markdown artifacts from model outputs.
    - Eliminates hardcoded static dashboard overrides.
    - Enforces size limits, content validation, and CSP headers for untrusted rendering.
    """

    # Basic tag patterns for detecting legitimate HTML
    HTML_BLOCK_REGEX = re.compile(r"```html\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
    MARKDOWN_BLOCK_REGEX = re.compile(r"```(?:markdown|md)\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
    RAW_HTML_REGEX = re.compile(r"(<!DOCTYPE html>.*?(?:</html>|$)|<html.*?>.*?(?:</html>|$))", re.DOTALL | re.IGNORECASE)

    def extract_or_create_artifact(
        self,
        session_id: str,
        content: str,
        title_hint: str = "Generated Artifact"
    ) -> Optional[Dict[str, Any]]:
        """
        Parses assistant content for codeblocks or document structures to create a sandboxed Artifact.
        Resilient against nested markdown fences and unclosed LLM codeblocks.
        """
        if not content or len(content.strip()) == 0:
            return None

        # Normalize nested/duplicate fences often emitted by local LLMs (e.g. ```html\n```html)
        cleaned_content = re.sub(r"```html\s*```(?:html)?", "```html", content, flags=re.IGNORECASE)
        cleaned_content = re.sub(r"```(?:markdown|md)\s*```(?:markdown|md)?", "```markdown", cleaned_content, flags=re.IGNORECASE)

        # 1. Check for closed ```html code block with substantive content
        for m in self.HTML_BLOCK_REGEX.finditer(cleaned_content):
            candidate = m.group(1).strip()
            candidate = re.sub(r"^```html\s*", "", candidate, flags=re.IGNORECASE).strip()
            if candidate and "<" in candidate:
                return self._build_artifact(
                    session_id=session_id,
                    title=self._format_title(title_hint, "HTML Component"),
                    artifact_type="html",
                    raw_content=candidate
                )

        # 2. Check for unclosed ```html block (when LLM generation reaches token limit)
        unclosed_html = re.search(r"```html\s*(.*)", cleaned_content, re.DOTALL | re.IGNORECASE)
        if unclosed_html:
            candidate = unclosed_html.group(1).strip()
            candidate = re.sub(r"^```html\s*", "", candidate, flags=re.IGNORECASE).strip()
            # Strip trailing partial backticks
            candidate = re.sub(r"```.*$", "", candidate, flags=re.DOTALL).strip()
            if candidate and "<" in candidate:
                return self._build_artifact(
                    session_id=session_id,
                    title=self._format_title(title_hint, "HTML Component"),
                    artifact_type="html",
                    raw_content=candidate
                )

        # 3. Check for raw HTML document in text
        raw_html_match = self.RAW_HTML_REGEX.search(cleaned_content)
        if raw_html_match:
            raw_code = raw_html_match.group(1).strip()
            if raw_code and len(raw_code) > 20:
                return self._build_artifact(
                    session_id=session_id,
                    title=self._format_title(title_hint, "HTML App"),
                    artifact_type="html",
                    raw_content=raw_code
                )

        # 4. Check for explicit ```markdown code block
        md_match = self.MARKDOWN_BLOCK_REGEX.search(cleaned_content)
        if md_match:
            md_code = md_match.group(1).strip()
            if md_code:
                return self._build_artifact(
                    session_id=session_id,
                    title=self._format_title(title_hint, "Markdown Document"),
                    artifact_type="markdown",
                    raw_content=md_code
                )

        # 5. Check for unclosed ```markdown block
        unclosed_md = re.search(r"```(?:markdown|md)\s*(.*)", cleaned_content, re.DOTALL | re.IGNORECASE)
        if unclosed_md:
            candidate_md = unclosed_md.group(1).strip()
            candidate_md = re.sub(r"```.*$", "", candidate_md, flags=re.DOTALL).strip()
            if candidate_md and len(candidate_md) > 100:
                return self._build_artifact(
                    session_id=session_id,
                    title=self._format_title(title_hint, "Markdown Document"),
                    artifact_type="markdown",
                    raw_content=candidate_md
                )

        # 6. Check for comprehensive Markdown essays or structured frameworks (e.g. Ship 30 essays)
        is_ship30_or_essay = (
            (title_hint and any(kw in title_hint.lower() for kw in ["ship 30", "essay", "playbook", "framework"]))
            or bool(re.search(r"(?i)(The Hook|The Trap|Paradigm Shift|Ship 30 for 30|1-Sentence Takeaway)", cleaned_content))
            or (("\n# " in cleaned_content or cleaned_content.startswith("# ")) and len(cleaned_content) > 400)
        )
        if is_ship30_or_essay and len(cleaned_content) > 150:
            return self._build_artifact(
                session_id=session_id,
                title=self._format_title(title_hint, "Growth Essay"),
                artifact_type="markdown",
                raw_content=cleaned_content
            )

        return None

    def create_dynamic_html_artifact(self, session_id: str, topic: str, html_content: str) -> Optional[Dict[str, Any]]:
        """Creates an artifact from dynamically generated HTML without hardcoded template overrides."""
        return self._build_artifact(
            session_id=session_id,
            title=f"{topic} (Interactive Artifact)",
            artifact_type="html",
            raw_content=html_content
        )

    def _build_artifact(
        self,
        session_id: str,
        title: str,
        artifact_type: str,
        raw_content: str
    ) -> Optional[Dict[str, Any]]:
        if not raw_content or not raw_content.strip():
            return None

        # Validate size
        content_bytes = raw_content.encode("utf-8")
        if len(content_bytes) > MAX_ARTIFACT_SIZE_BYTES:
            logger.warning(f"Artifact content exceeds size limit ({len(content_bytes)} bytes). Truncating.")
            raw_content = content_bytes[:MAX_ARTIFACT_SIZE_BYTES].decode("utf-8", errors="ignore")

        # Sanitize HTML artifacts by injecting a Restrictive Content Security Policy
        secured_content = raw_content
        if artifact_type == "html":
            secured_content = self._inject_security_headers(raw_content)

        return {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "title": title[:255],
            "artifact_type": artifact_type,
            "content": secured_content
        }

    def _inject_security_headers(self, html: str) -> str:
        """
        Injects a strict Content Security Policy (CSP) meta tag into the HTML document.
        Disallows top-navigation, external networking, and frame embedding from other origins.
        """
        csp_meta = (
            '<meta http-equiv="Content-Security-Policy" content="'
            "default-src 'none'; "
            "style-src 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; "
            "script-src 'unsafe-inline'; "
            "img-src data: https:; "
            "connect-src 'none'; "
            "frame-src 'none'; "
            '">'
        )

        if "<head>" in html.lower():
            return re.sub(r"(<head.*?>)", r"\1\n  " + csp_meta, html, count=1, flags=re.IGNORECASE)
        elif "<html" in html.lower():
            return re.sub(r"(<html.*?>)", r"\1\n<head>\n  " + csp_meta + "\n</head>", html, count=1, flags=re.IGNORECASE)
        else:
            return f"<!DOCTYPE html>\n<html>\n<head>\n  {csp_meta}\n</head>\n<body>\n{html}\n</body>\n</html>"

    def _format_title(self, hint: str, suffix: str) -> str:
        clean = re.sub(r"[#*_`]", "", hint).strip()
        if len(clean) > 35:
            clean = clean[:35] + "..."
        return f"{clean} ({suffix})"

artifact_generator = ArtifactGenerator()
