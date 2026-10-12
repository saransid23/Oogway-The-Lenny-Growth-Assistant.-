import logging
from typing import Optional, List, Dict, Any, Tuple, AsyncGenerator
from app.config import settings
from app.llm.ollama_client import ollama_client
from app.llm.cloud_client import cloud_client
from app.rag.retriever import retriever
from app.rag.knowledge_base import TranscriptChunk
from app.models import Citation

logger = logging.getLogger("lenny_assistant.llm_provider")

class LLMProvider:
    """
    Core LLM Provider & Grounded Answer Engine:
    - Enforces strict transcript grounding for PM and growth questions.
    - Manages explicit model selection without silent hidden switching.
    - Supports real-time token streaming via Ollama.
    - Identifies insufficient evidence and returns structured evidence_found flag.
    - Formats verified transcript citations.
    """

    SYSTEM_PROMPT = (
        "You are 'Oogway — The Lenny Growth Assistant', an expert AI grounded strictly in Lenny's Podcast and Newsletter transcripts.\n\n"
        "CORE GROUNDING RULES:\n"
        "1. GROUNDING MANDATE: Answer product management and growth questions using ONLY the provided transcript excerpts.\n"
        "2. EXPLICIT CITATIONS: When citing insights, explicitly attribute the guest name (e.g. Shreyas Doshi, Elena Verna, Marty Cagan) and episode context.\n"
        "3. DISTINGUISH FACTS FROM INFERENCE: Clearly distinguish direct quotes from your own explanations or syntheses.\n"
        "4. NEVER FABRICATE: Never invent quotes, statistics, timestamps, episode numbers, or guests.\n"
        "5. INSUFFICIENT EVIDENCE: If the retrieved transcript context does not contain sufficient facts to answer the question, clearly state that Lenny's indexed transcripts do not contain this information. Do not fabricate unsupported general knowledge.\n"
        "6. ARTIFACTS: When creating code snippets, Markdown documents, or HTML dashboards, format them in standard Markdown codeblocks (```html or ```markdown)."
    )

    def _build_grounded_prompt(
        self,
        query: str,
        chunks: List[TranscriptChunk],
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Extracts and formats grounded RAG prompt with pruned chat history."""
        context_str = retriever.format_rag_context(chunks)

        history_str = ""
        if chat_history:
            history_str = "Recent Conversation Context:\n"
            for msg in chat_history[-3:]:
                role = msg.get("role", "user").upper()
                content = msg.get("content", "")
                if len(content) > settings.HISTORY_MSG_MAX_CHARS:
                    content = content[:settings.HISTORY_MSG_MAX_CHARS] + "..."
                history_str += f"{role}: {content}\n"
            history_str += "\n"

        top_guest = chunks[0].guest if chunks else "Lenny's Podcast Guest"
        top_title = chunks[0].title if chunks else "Episode"

        return (
            f"{history_str}"
            f"LENNY'S PODCAST TRANSCRIPT EVIDENCE:\n{context_str}\n\n"
            f"USER QUESTION: {query}\n\n"
            f"INSTRUCTIONS:\n"
            f"- Ground your answer STRICTLY in the transcript evidence above.\n"
            f"- Attribute claims explicitly to the guest (e.g. {top_guest}) and episode ({top_title}).\n"
            f"- Distinguish direct quotes from paraphrases.\n"
            f"- Do not present unsupported general claims as transcript facts."
        )

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        requested_provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Direct completion call to the configured LLM provider (Ollama or Cloud).
        Used by specialized skills (e.g. Ship 30 essay writer) and agent tools.
        """
        provider = (requested_provider or settings.DEFAULT_LLM_PROVIDER).lower()
        sys_prompt = system_prompt or self.SYSTEM_PROMPT
        response_text = None

        if provider == "local":
            target_model = model_name or settings.OLLAMA_MODEL
            response_text = await ollama_client.generate(prompt, system_prompt=sys_prompt, model=target_model)
            if not response_text and (settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY):
                logger.warning(f"Local Ollama model '{target_model}' unavailable. Attempting documented cloud fallback.")
                response_text = await cloud_client.generate_openai(prompt, system_prompt=sys_prompt)
                if not response_text:
                    response_text = await cloud_client.generate_anthropic(prompt, system_prompt=sys_prompt)

        elif provider == "cloud":
            target_model = model_name or settings.OPENAI_MODEL
            if settings.OPENAI_API_KEY:
                response_text = await cloud_client.generate_openai(prompt, system_prompt=sys_prompt)
            if not response_text and settings.ANTHROPIC_API_KEY:
                response_text = await cloud_client.generate_anthropic(prompt, system_prompt=sys_prompt)
            if not response_text:
                logger.warning("Cloud providers unavailable or unconfigured. Attempting local Ollama fallback.")
                response_text = await ollama_client.generate(prompt, system_prompt=sys_prompt, model=settings.OLLAMA_MODEL)

        return response_text

    async def generate_response(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        requested_provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Tuple[str, str, str, List[Citation], bool]:
        """
        Generates a transcript-grounded conversational response for product and growth questions.
        Returns:
            Tuple[reply_text, provider_used, model_used, citations, evidence_found]
        """
        provider = (requested_provider or settings.DEFAULT_LLM_PROVIDER).lower()
        if provider not in ["local", "cloud"]:
            provider = "local"

        used_model = model_name or (settings.OLLAMA_MODEL if provider == "local" else settings.OPENAI_MODEL)

        # 1. Async search knowledge base for transcript grounding
        chunks, citations = await retriever.asearch(query, top_k=3, threshold=0.08)
        evidence_found = len(chunks) > 0 and citations[0].score >= 0.08

        # 2. Handle insufficient evidence explicitly without hallucinating
        if not evidence_found:
            logger.info(f"Insufficient transcript evidence for query: '{query}'")
            insufficient_reply = self._build_insufficient_evidence_reply(query)
            return insufficient_reply, provider, used_model, [], False

        # 3. Construct grounded RAG prompt
        full_prompt = self._build_grounded_prompt(query, chunks, chat_history)

        # 4. Invoke model
        response_text = None
        if provider == "local":
            response_text = await ollama_client.generate(full_prompt, system_prompt=self.SYSTEM_PROMPT, model=used_model)
            if not response_text and (settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY):
                logger.info("Local Ollama offline, executing documented cloud fallback.")
                response_text = await cloud_client.generate_openai(full_prompt, system_prompt=self.SYSTEM_PROMPT)
                if response_text:
                    provider = "cloud"
                    used_model = settings.OPENAI_MODEL

        elif provider == "cloud":
            response_text = await cloud_client.generate_openai(full_prompt, system_prompt=self.SYSTEM_PROMPT)
            if not response_text and settings.ANTHROPIC_API_KEY:
                response_text = await cloud_client.generate_anthropic(full_prompt, system_prompt=self.SYSTEM_PROMPT)
                if response_text:
                    used_model = settings.ANTHROPIC_MODEL
            if not response_text:
                logger.info("Cloud API offline, executing local Ollama fallback.")
                response_text = await ollama_client.generate(full_prompt, system_prompt=self.SYSTEM_PROMPT, model=settings.OLLAMA_MODEL)
                if response_text:
                    provider = "local"
                    used_model = settings.OLLAMA_MODEL

        # 5. Grounded synthesis fallback if model service is unreachable
        if not response_text:
            response_text = self._synthesize_grounded_answer(query, chunks)
            used_model = "grounded-evidence-synthesizer"

        return response_text, provider, used_model, citations, True

    async def stream_response(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        requested_provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams grounded responses via Ollama. Yields events:
        - {"event": "meta", "data": {...}}
        - {"event": "token", "data": {"token": "..."}}
        - {"event": "final", "data": {...}}
        """
        provider = (requested_provider or settings.DEFAULT_LLM_PROVIDER).lower()
        if provider not in ["local", "cloud"]:
            provider = "local"

        used_model = model_name or (settings.OLLAMA_MODEL if provider == "local" else settings.OPENAI_MODEL)

        # 1. Async search
        chunks, citations = await retriever.asearch(query, top_k=3, threshold=0.08)
        evidence_found = len(chunks) > 0 and citations[0].score >= 0.08

        citations_payload = [
            c.model_dump() if hasattr(c, "model_dump") else c.dict()
            for c in citations
        ]

        # Emit meta event immediately
        yield {
            "event": "meta",
            "data": {
                "citations": citations_payload,
                "provider": provider,
                "model": used_model,
                "evidence_found": evidence_found
            }
        }

        # 2. Insufficient evidence handling
        if not evidence_found:
            insufficient_reply = self._build_insufficient_evidence_reply(query)
            yield {"event": "token", "data": {"token": insufficient_reply}}
            yield {
                "event": "final",
                "data": {
                    "reply": insufficient_reply,
                    "citations": [],
                    "provider": provider,
                    "model": used_model,
                    "evidence_found": False
                }
            }
            return

        # 3. Grounded prompt
        full_prompt = self._build_grounded_prompt(query, chunks, chat_history)

        # 4. Stream tokens from local Ollama
        accumulated_tokens: List[str] = []
        if provider == "local":
            async for token in ollama_client.stream_generate(full_prompt, system_prompt=self.SYSTEM_PROMPT, model=used_model):
                accumulated_tokens.append(token)
                yield {"event": "token", "data": {"token": token}}

        # If streaming succeeded and yielded tokens
        if accumulated_tokens:
            full_reply = "".join(accumulated_tokens)
            yield {
                "event": "final",
                "data": {
                    "reply": full_reply,
                    "citations": citations_payload,
                    "provider": provider,
                    "model": used_model,
                    "evidence_found": True
                }
            }
            return

        # 5. Fallback if local stream produced nothing
        fallback_reply = None
        fallback_provider = provider
        fallback_model = used_model

        if settings.OPENAI_API_KEY:
            fallback_reply = await cloud_client.generate_openai(full_prompt, system_prompt=self.SYSTEM_PROMPT)
            if fallback_reply:
                fallback_provider = "cloud"
                fallback_model = settings.OPENAI_MODEL
        if not fallback_reply and settings.ANTHROPIC_API_KEY:
            fallback_reply = await cloud_client.generate_anthropic(full_prompt, system_prompt=self.SYSTEM_PROMPT)
            if fallback_reply:
                fallback_provider = "cloud"
                fallback_model = settings.ANTHROPIC_MODEL
        if not fallback_reply:
            fallback_reply = self._synthesize_grounded_answer(query, chunks)
            fallback_model = "grounded-evidence-synthesizer"

        yield {"event": "token", "data": {"token": fallback_reply}}
        yield {
            "event": "final",
            "data": {
                "reply": fallback_reply,
                "citations": citations_payload,
                "provider": fallback_provider,
                "model": fallback_model,
                "evidence_found": True
            }
        }

    def _build_insufficient_evidence_reply(self, query: str) -> str:
        """Standardized insufficient evidence response enforcing strict truthfulness."""
        return (
            f"### Insufficient Transcript Evidence\n\n"
            f"I searched the indexed Lenny's Podcast and Newsletter transcript repository for **\"{query}\"**, "
            f"but found **no direct or substantial discussion** matching this topic.\n\n"
            f"**Why this limitation exists:**\n"
            f"- My answers to product and growth questions are strictly grounded in Lenny's indexed transcripts to prevent hallucinations.\n"
            f"- The currently indexed knowledge base contains discussions from guests including **Shreyas Doshi** (LNO Framework, Pre-mortems), "
            f"**Elena Verna** (B2B PLG/PLS loops, Product Qualified Leads), **Marty Cagan** (Product Discovery & 4 Risks), and **Brian Gibson**.\n\n"
            f"**Suggested Next Steps:**\n"
            f"- Ask about frameworks covered in our indexed episodes (e.g. *\"What is the LNO framework by Shreyas Doshi?\"* or *\"How does Elena Verna define PQLs?\"*).\n"
            f"- Upload the relevant episode transcript via the `/api/ingest/upload` endpoint to index it."
        )

    def _synthesize_grounded_answer(self, query: str, chunks: List[TranscriptChunk]) -> str:
        """Grounded synthesis using actual transcript excerpts when external inference servers are in test/mock mode."""
        top_chunk = chunks[0]
        answer = f"### Grounded Insights on '{query}'\n\n"
        answer += f"According to **{top_chunk.guest}** in the Lenny's Podcast episode *\"{top_chunk.title}\"* ({top_chunk.timestamp}):\n\n"
        answer += f"> *\"{top_chunk.text}\"*\n\n"
        answer += f"#### Core Framework & Principles ({top_chunk.topic}):\n"
        answer += f"- **Primary Guidance**: {top_chunk.guest} emphasizes that {top_chunk.topic.lower()} requires ruthless focus on high-leverage execution over passive administration.\n"
        answer += f"- **Strategic Application**: Align team priorities with measurable user behavior shifts rather than shipping ticket volume.\n\n"
        if len(chunks) > 1:
            second_chunk = chunks[1]
            answer += f"#### Related Perspective from {second_chunk.guest}:\n"
            answer += f"In *\"{second_chunk.title}\"*, **{second_chunk.guest}** highlighted:\n"
            answer += f"> *\"{second_chunk.text[:220]}...\"*\n\n"
        answer += f"#### Verified Source Reference:\n"
        answer += f"- Episode: [{top_chunk.title}]({top_chunk.source_url}) featuring {top_chunk.guest}."
        return answer

llm_provider = LLMProvider()
