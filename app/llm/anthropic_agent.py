import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from app.config import settings
from app.rag.retriever import retriever
from app.models import Citation
from app.skills.ship30 import ship30_skill

try:
    import anthropic
    from anthropic import AsyncAnthropic
except ImportError:
    anthropic = None
    AsyncAnthropic = None

try:
    import claude_agent_sdk
except ImportError:
    claude_agent_sdk = None

logger = logging.getLogger("lenny_assistant.anthropic_agent")

# Bounded execution constraints
MAX_TOOL_ITERATIONS = 3
TOOL_TIMEOUT_SECONDS = 30.0

CLAUDE_AGENT_TOOLS = [
    {
        "name": "search_transcripts",
        "description": "Searches Lenny's Podcast and Newsletter transcript repository for grounded product and growth insights from guests (e.g. Elena Verna, Shreyas Doshi, Marty Cagan). Returns topic excerpts, timestamps, and quotes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query or growth framework (e.g. 'LNO framework', 'B2B PLG loops', 'product discovery risks')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "generate_ship30_essay",
        "description": "Generates a structured, highly actionable ~1,250-word masterclass essay formatted following Ship 30 for 30 principles (Hook, Trap, Paradigm Shift, 3 Rules, Actionable Takeaway).",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Product management or growth topic to write the essay on."
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "create_artifact",
        "description": "Generates a complete, interactive HTML/CSS dashboard or Markdown document for side-by-side rendering in the In-App Artifact Viewer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the artifact."
                },
                "artifact_type": {
                    "type": "string",
                    "enum": ["html", "markdown"],
                    "description": "Type of artifact to generate."
                },
                "content": {
                    "type": "string",
                    "description": "Complete HTML or Markdown content."
                }
            },
            "required": ["title", "artifact_type", "content"]
        }
    }
]

class AnthropicClaudeAgent:
    """
    Anthropic Agent Integration Layer:
    - Provides autonomous tool-use orchestration using AsyncAnthropic with Claude 3.5 Sonnet.
    - Implements bounded iterations, strict timeouts, cancellation safety, and error trapping.
    - Registered tools:
        1. search_transcripts: Grounded RAG retrieval with citations
        2. generate_ship30_essay: Ship 30 writing workflow
        3. create_artifact: Dynamic artifact synthesis
    - Restricts filesystem access: Tools only access in-memory RAG index and sanitized artifact objects.
    """

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.client: Optional[AsyncAnthropic] = None
        if self.api_key and AsyncAnthropic:
            try:
                self.client = AsyncAnthropic(api_key=self.api_key)
                logger.info("Initialized Anthropic Claude Agent SDK execution client")
            except Exception as e:
                logger.warning(f"Could not initialize AsyncAnthropic: {e}")

    def is_available(self) -> bool:
        return bool(self.api_key and self.client)

    async def run_agent(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> Optional[Tuple[str, List[Citation]]]:
        """
        Executes a bounded agentic tool-use cycle.
        Returns:
            Tuple[reply_text, citations] or None if unavailable.
        """
        if not self.is_available():
            return None

        sys_prompt = system_prompt or (
            "You are an evidence-grounded AI growth and product assistant for Lenny's Podcast.\n"
            "MANDATE: Ground all product and growth answers strictly in Lenny's transcript corpus.\n"
            "Always use `search_transcripts` to look up source evidence before answering factual questions.\n"
            "If the user asks for a Ship 30 essay, call the `generate_ship30_essay` tool.\n"
            "If the user asks for an interactive dashboard or mockup, call the `create_artifact` tool."
        )

        messages = []
        if chat_history:
            for msg in chat_history[-3:]:
                role = "assistant" if msg["role"] == "assistant" else "user"
                messages.append({"role": role, "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})
        accumulated_citations: List[Citation] = []

        try:
            # Wrap execution with timeout to prevent hung requests
            return await asyncio.wait_for(
                self._execute_agent_loop(messages, sys_prompt, accumulated_citations, user_message),
                timeout=TOOL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error(f"Claude Agent execution timed out after {TOOL_TIMEOUT_SECONDS}s")
            return None
        except Exception as e:
            logger.error(f"Claude Agent execution error: {e}")
            return None

    async def _execute_agent_loop(
        self,
        messages: List[Dict[str, Any]],
        sys_prompt: str,
        accumulated_citations: List[Citation],
        original_query: str
    ) -> Tuple[str, List[Citation]]:
        
        response = await self.client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2048,
            system=sys_prompt,
            messages=messages,
            tools=CLAUDE_AGENT_TOOLS
        )

        iteration = 0
        while response.stop_reason == "tool_use" and iteration < MAX_TOOL_ITERATIONS:
            iteration += 1
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tool_call in tool_use_blocks:
                tool_name = tool_call.name
                tool_args = tool_call.input or {}
                tool_id = tool_call.id

                logger.info(f"Claude Agent executing tool '{tool_name}' (iteration {iteration})")

                if tool_name == "search_transcripts":
                    query = tool_args.get("query", original_query)
                    chunks, citations = await retriever.asearch(query, top_k=3, threshold=0.08)
                    accumulated_citations.extend(citations)
                    result_str = retriever.format_rag_context(chunks)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_str
                    })

                elif tool_name == "generate_ship30_essay":
                    topic = tool_args.get("topic", original_query)
                    essay_text, citations = await ship30_skill.generate_essay(topic=topic)
                    accumulated_citations.extend(citations)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": essay_text
                    })

                elif tool_name == "create_artifact":
                    title = tool_args.get("title", "Generated Artifact")
                    artifact_type = tool_args.get("artifact_type", "html")
                    content = tool_args.get("content", "")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": f"Artifact created successfully: [{title}] ({artifact_type})\n```{artifact_type}\n{content}\n```"
                    })

                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": f"Error: Unknown tool '{tool_name}'"
                    })

            messages.append({"role": "user", "content": tool_results})

            response = await self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2048,
                system=sys_prompt,
                messages=messages,
                tools=CLAUDE_AGENT_TOOLS
            )

        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        final_reply = "".join(text_blocks).strip()
        return final_reply, accumulated_citations

claude_agent = AnthropicClaudeAgent()
