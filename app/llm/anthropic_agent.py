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

logger = logging.getLogger("lenny_assistant.anthropic_agent")

# Anthropic Tool Definitions for Claude Agent Layer
CLAUDE_AGENT_TOOLS = [
    {
        "name": "search_transcripts",
        "description": "Searches Lenny's Podcast and Newsletter transcript repository for grounded product and growth insights from guests (e.g. Elena Verna, Shreyas Doshi, Marty Cagan). Returns topic excerpts, timestamps, and quotes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keywords or framework query (e.g. 'LNO framework', 'Elena Verna PLG loops', 'product discovery risks')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "generate_ship30_essay",
        "description": "Generates a structured, highly actionable ~1,250-word masterclass essay formatted following Ship 30 for 30 principles (Hook, 3 Core Rules, Mistakes, Action Plan, Takeaway).",
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
    }
]

class AnthropicClaudeAgent:
    """
    Anthropic Claude Agent SDK Integration Layer.
    Executes an autonomous tool-calling loop using AsyncAnthropic.
    Tools:
      - search_transcripts: Grounds output using Lenny's podcast transcript index
      - generate_ship30_essay: Synthesizes structured Ship 30 frameworks
    """

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.client: Optional[AsyncAnthropic] = None
        if self.api_key and AsyncAnthropic:
            try:
                self.client = AsyncAnthropic(api_key=self.api_key)
                logger.info("Initialized Anthropic Claude Agent SDK client")
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
        Executes an agentic tool-use cycle with Claude 3.5 Sonnet.
        Returns (reply_text, citations) or None if client unavailable.
        """
        if not self.is_available():
            return None

        sys_prompt = system_prompt or (
            "You are an evidence-grounded AI growth and product assistant for Lenny's Podcast.\n"
            "Always use the `search_transcripts` tool when users ask about product, growth, or guest frameworks.\n"
            "Ground your answers directly in the retrieved excerpts and cite guests accurately."
        )

        messages = []
        if chat_history:
            for msg in chat_history[-4:]:
                role = "assistant" if msg["role"] == "assistant" else "user"
                messages.append({"role": role, "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        accumulated_citations: List[Citation] = []

        try:
            # Step 1: Initial call with tools
            response = await self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2048,
                system=sys_prompt,
                messages=messages,
                tools=CLAUDE_AGENT_TOOLS
            )

            # Step 2: Handle Tool Calls Loop (up to 2 iterations)
            iterations = 0
            while response.stop_reason == "tool_use" and iterations < 2:
                iterations += 1
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                
                # Append assistant's tool-call response to thread
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for tool_call in tool_use_blocks:
                    tool_name = tool_call.name
                    tool_args = tool_call.input or {}
                    tool_id = tool_call.id

                    logger.info(f"Claude Agent executing tool '{tool_name}' with args {tool_args}")

                    if tool_name == "search_transcripts":
                        query = tool_args.get("query", user_message)
                        chunks, citations = retriever.search(query, top_k=3)
                        accumulated_citations.extend(citations)
                        result_str = retriever.format_rag_context(chunks)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result_str
                        })

                    elif tool_name == "generate_ship30_essay":
                        topic = tool_args.get("topic", user_message)
                        essay_text, citations = await ship30_skill.generate_essay(topic=topic)
                        accumulated_citations.extend(citations)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": essay_text
                        })

                    else:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"Unknown tool: {tool_name}"
                        })

                # Append tool result messages
                messages.append({"role": "user", "content": tool_results})

                # Follow-up completion after tool execution
                response = await self.client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=2048,
                    system=sys_prompt,
                    messages=messages,
                    tools=CLAUDE_AGENT_TOOLS
                )

            # Extract final text
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            final_reply = "".join(text_blocks).strip()
            return final_reply, accumulated_citations

        except Exception as e:
            logger.error(f"Anthropic Claude Agent SDK execution error: {e}")
            return None

claude_agent = AnthropicClaudeAgent()
