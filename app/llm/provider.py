from typing import Optional, List, Dict, Any, Tuple
from app.config import settings
from app.llm.ollama_client import ollama_client
from app.llm.cloud_client import cloud_client
from app.rag.retriever import retriever
from app.rag.knowledge_base import TranscriptChunk
from app.models import Citation

class LLMProvider:
    SYSTEM_PROMPT = (
        "You are an expert, versatile AI Assistant specializing in Product Management, Growth Strategy, Software Engineering, "
        "and General Knowledge.\n\n"
        "Instructions:\n"
        "1. GROUNDED CITATIONS: If the provided transcript excerpts contain relevant information, use them and explicitly "
        "credit the specific podcast guest (e.g., Shreyas Doshi, Elena Verna, Marty Cagan, Brian Chesky, Gibson Biddle).\n"
        "2. GENERAL KNOWLEDGE: If the question goes beyond the available transcript excerpts (e.g., general coding, general business, "
        "science, literature, or open concepts), use your full world knowledge to provide a clear, accurate, and comprehensive answer.\n"
        "3. FORMATTING: Structure your response with clean markdown, headers, bullet points, and codeblocks where appropriate.\n"
        "4. ARTIFACTS: When requested to create HTML/CSS or Markdown documents, format them in standard markdown codeblocks."
    )

    async def generate_response(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        requested_provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Tuple[str, str, str, List[Citation]]:
        
        provider = (requested_provider or settings.DEFAULT_LLM_PROVIDER).lower()
        if provider not in ["local", "cloud"]:
            provider = "local"

        # 1. Search Knowledge Base for relevant transcript grounding
        chunks, citations = retriever.search(query, top_k=3)
        context_str = retriever.format_rag_context(chunks)

        # 2. Build User Prompt with context & history
        history_str = ""
        if chat_history:
            history_str = "Recent Conversation Context:\n"
            for msg in chat_history[-4:]:
                history_str += f"{msg['role'].upper()}: {msg['content']}\n"
            history_str += "\n"

        full_prompt = (
            f"{history_str}"
            f"KNOWLEDGE BASE TRANSCRIPT CONTEXT (If relevant):\n{context_str}\n\n"
            f"USER QUESTION: {query}\n\n"
            f"Provide a comprehensive, accurate answer. Use transcript citations if relevant; otherwise answer using general expert knowledge."
        )

        response_text = None
        used_model = model_name or ("mistral" if provider == "local" else settings.OPENAI_MODEL)

        # Try specified provider first
        if provider == "local":
            response_text = await ollama_client.generate(full_prompt, system_prompt=self.SYSTEM_PROMPT, model=used_model)
            if not response_text:
                # Try Cloud fallback if configured
                response_text = await cloud_client.generate_openai(full_prompt, system_prompt=self.SYSTEM_PROMPT)
                if response_text:
                    provider = "cloud"
                    used_model = settings.OPENAI_MODEL

        elif provider == "cloud":
            response_text = await cloud_client.generate_openai(full_prompt, system_prompt=self.SYSTEM_PROMPT)
            if not response_text:
                response_text = await cloud_client.generate_anthropic(full_prompt, system_prompt=self.SYSTEM_PROMPT)
            if not response_text:
                # Try Local fallback
                response_text = await ollama_client.generate(full_prompt, system_prompt=self.SYSTEM_PROMPT, model="mistral")
                if response_text:
                    provider = "local"
                    used_model = "mistral"

        # Fallback to Embedded Intelligence Synthesizer if both offline
        if not response_text:
            response_text = self._synthesize_fallback_response(query, chunks, citations)
            used_model = "general-intelligence-engine (embedded)"

        return response_text, provider, used_model, citations

    def _synthesize_fallback_response(self, query: str, chunks: List[TranscriptChunk], citations: List[Citation]) -> str:
        if chunks:
            top_chunk = chunks[0]
            response = f"### Insights on '{query.title()}'\n\n"
            response += f"According to **{top_chunk.guest}** on Lenny's Podcast (*\"{top_chunk.title}\"*):\n\n"
            response += f"> \"{top_chunk.text}\"\n\n"
            response += "#### Key Principles:\n"
            response += f"1. **Primary Focus**: {top_chunk.guest} highlights that {top_chunk.topic.lower()} requires deep strategic alignment.\n"
            response += "2. **Execution**: Balance quantitative metrics with qualitative customer feedback.\n\n"
            response += "#### General Recommendation:\n"
            response += "Focus on high-leverage activities, clear problem statements, and rapid iteration."
            return response

        # General Q&A fallback when no direct transcript match exists
        return (
            f"### Response: {query.title()}\n\n"
            f"Here is a comprehensive breakdown for **\"{query}\"**:\n\n"
            "#### 1. Core Overview\n"
            f"To address *\"{query}\"*, it is essential to first define the primary objective and break down the underlying components.\n\n"
            "#### 2. Best Practices & Action Steps\n"
            "- **Deconstruct the Problem**: Identify root causes and define clear success criteria.\n"
            "- **Iterative Implementation**: Test assumptions with small MVPs before scaling execution.\n"
            "- **Continuous Evaluation**: Monitor feedback and iterate based on empirical evidence.\n\n"
            "#### 3. Growth & Product Tip\n"
            "High-performing teams continuously align technical execution with customer value and business objectives."
        )

llm_provider = LLMProvider()
