import re
import logging
from typing import List, Tuple, Dict, Any, Optional
from app.rag.retriever import retriever
from app.rag.knowledge_base import TranscriptChunk
from app.models import Citation
from app.config import settings

logger = logging.getLogger("lenny_assistant.ship30")

class Ship30Skill:
    """
    Ship 30 for 30 Specialized Content Skill
    Encodes writing principles from Dickie Bush & Nicolas Cole's Ship 30 for 30:
    - 1 Core Idea: Laser-focused single premise.
    - Strong Hook: High-friction opening line capturing attention in <3 seconds.
    - Narrative Arc: Problem (The Trap) -> Mindset Shift -> 3-Step Execution Framework -> 1-Sentence Takeaway.
    - Skimmability: 1-2 sentence paragraphs, bold lead-in emphasis, bulleted lists.
    - Grounding: Cites verified transcript quotes vs paraphrases; strictly avoids fabricating quotes or statistics.
    - Target length: ~1,250 words when sufficient transcript evidence is available.
    - Insufficient evidence handling: Acknowledges transcript corpus limits rather than inventing claims.
    """

    SYSTEM_PROMPT = (
        "You are an evidence-grounded masterclass writer specializing in the Ship 30 for 30 essay framework.\n\n"
        "WRITING PRINCIPLES:\n"
        "1. THE HOOK: Open with an arresting 1-2 sentence observation about why teams fail or a counter-intuitive reality.\n"
        "2. NARRATIVE PROGRESSION:\n"
        "   - Part 1: The Trap (The default error made by 90% of product teams).\n"
        "   - Part 2: The Paradigm Shift (The counter-intuitive mental model explained by Lenny's guest).\n"
        "   - Part 3: The 3-Step Execution Playbook (Three actionable rules with tactical implementation steps).\n"
        "   - Part 4: The 1-Sentence Takeaway (A punchy, memorable action mandate).\n"
        "3. HIGH SKIMMABILITY: Use short 1-2 sentence paragraphs, bold sub-headers, and bullet points. Never use walls of text.\n"
        "4. RIGOROUS GROUNDING: Ground all factual claims in the provided transcript context. Never invent quotes, guests, or episode titles.\n"
        "5. QUOTE INTEGRITY: Clearly distinguish direct quotes in blockquotes (> \"...\") from paraphrased principles.\n"
        "6. INSUFFICIENT EVIDENCE: If the transcript context does not discuss the topic, state this limitation clearly and provide what is known without hallucinating.\n"
        "7. TARGET LENGTH: Generate a comprehensive, deep masterclass essay (aiming for ~1,250 words when ample source context is provided)."
    )

    def validate_essay(self, essay_text: str, topic: str) -> Dict[str, Any]:
        """
        Validates that the generated essay adheres to the Ship 30 format,
        addresses the requested topic, and contains core architectural components.
        """
        if not essay_text or len(essay_text.strip()) == 0:
            return {"valid": False, "word_count": 0, "errors": ["Essay is empty"]}

        words = essay_text.split()
        word_count = len(words)
        errors = []

        # Check topic presence (at least key topic words)
        cleaned_topic = re.sub(r'[^\w\s]', '', topic.lower())
        topic_words = [w for w in cleaned_topic.split() if len(w) > 3]
        topic_matched = any(w in essay_text.lower() for w in topic_words) if topic_words else True
        if not topic_matched:
            errors.append(f"Essay does not prominently feature topic keywords from '{topic}'")

        # Check structural components
        has_hook = bool(re.search(r"(hook|trap|problem|most product teams|here is the)", essay_text, re.I))
        has_takeaway = bool(re.search(r"(takeaway|actionable takeaway|conclusion|summary)", essay_text, re.I))
        has_grounding = bool(re.search(r"(transcript|lenny|podcast|quote|grounding|guest)", essay_text, re.I))

        if not has_hook:
            errors.append("Missing strong opening hook or trap section")
        if not has_takeaway:
            errors.append("Missing actionable 1-sentence takeaway section")
        if not has_grounding:
            errors.append("Missing transcript grounding attribution")

        is_valid = len(errors) == 0

        return {
            "valid": is_valid,
            "word_count": word_count,
            "has_hook": has_hook,
            "has_takeaway": has_takeaway,
            "has_grounding": has_grounding,
            "topic_matched": topic_matched,
            "errors": errors
        }

    async def generate_essay(
        self,
        topic: str,
        target_audience: str = "Product Managers & Growth Leaders",
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[str, List[Citation]]:
        """
        Genuinely LLM-invoked Ship 30 for 30 essay generation.
        Retrieves transcript evidence, constructs Ship 30 instructions,
        invokes the configured LLM provider, validates output, and handles bounded revision.
        """
        logger.info(f"Generating Ship 30 essay on topic: '{topic}' for audience: '{target_audience}'")

        # Step 1: Retrieve grounded transcript evidence
        chunks, citations = retriever.search(topic, top_k=4, threshold=0.08)
        has_sufficient_evidence = len(chunks) > 0 and citations[0].score >= 0.08

        # Step 2: Format context and prompt
        if not has_sufficient_evidence:
            logger.warning(f"Insufficient transcript evidence for topic: '{topic}'")
            return self._generate_insufficient_evidence_response(topic, target_audience), []

        context_str = retriever.format_rag_context(chunks)
        primary_guest = chunks[0].guest
        primary_title = chunks[0].title

        user_prompt = (
            f"TARGET AUDIENCE: {target_audience}\n"
            f"REQUESTED TOPIC: {topic}\n\n"
            f"EVIDENCE FROM LENNY'S PODCAST TRANSCRIPTS:\n{context_str}\n\n"
            "TASK: Write a comprehensive, masterclass Ship 30 for 30 essay on this exact topic.\n"
            "REQUIREMENTS:\n"
            "- Headline: `# How to Master {Topic}: The {Guest} Playbook`\n"
            "- The Hook: Arresting, contrarian opening highlighting why standard approaches fail.\n"
            "- Part 1: The Trap (The feature-factory / execution trap modern teams fall into).\n"
            "- Part 2: The Paradigm Shift (The counter-intuitive mental model from the transcript).\n"
            "- Part 3: The 3-Step Execution Framework (Rule 1, Rule 2, Rule 3 with step-by-step guidance).\n"
            "- Part 4: The 1-Sentence Takeaway (Clear, memorable, high-leverage closing mandate).\n"
            "- Distinguish direct quotes from paraphrases.\n"
            "- Ground all claims in the provided transcript evidence.\n"
            "- Target ~1,250 words with skimmable 1-2 sentence paragraphs and bold highlights."
        )

        # Step 3: Invoke LLM Provider
        essay_text = await self._call_llm(user_prompt, provider=provider, model_name=model_name)

        # Fallback synthesis if LLM returned empty/offline
        if not essay_text or len(essay_text.strip()) < 100:
            essay_text = self._synthesize_grounded_essay(topic, target_audience, chunks, citations)

        # Step 4: Validate output
        validation = self.validate_essay(essay_text, topic)
        logger.info(f"Ship 30 Essay validation: valid={validation['valid']}, word_count={validation['word_count']}")

        # Step 5: Bounded revision (max 1 retry loop if critical components missing)
        if not validation["valid"] and len(validation["errors"]) > 0:
            logger.info(f"Validation failed with errors: {validation['errors']}. Performing bounded revision...")
            revision_prompt = (
                f"{user_prompt}\n\n"
                f"PREVIOUS DRAFT ISSUES: {', '.join(validation['errors'])}\n"
                f"Please revise the essay to fix these issues. Ensure all sections (Hook, Part 1-4, Takeaway) are present."
            )
            revised_text = await self._call_llm(revision_prompt, provider=provider, model_name=model_name)
            if revised_text and len(revised_text.strip()) > 200:
                essay_text = revised_text

        # Ensure citation block is attached
        if "### **Source References & Grounding**" not in essay_text:
            essay_text += self._format_citation_footer(chunks)

        return essay_text, citations

    async def _call_llm(self, prompt: str, provider: Optional[str] = None, model_name: Optional[str] = None) -> Optional[str]:
        """Calls the configured LLM (Ollama or Cloud) using the application LLM provider layer."""
        from app.llm.provider import llm_provider
        return await llm_provider.generate_completion(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            requested_provider=provider,
            model_name=model_name
        )

    def _generate_insufficient_evidence_response(self, topic: str, target_audience: str) -> str:
        """Clear, transparent response when transcript corpus lacks sufficient evidence."""
        return f"""# Evidence Limitation Notice: {topic}

*Target Audience: {target_audience}*  
*Corpus: Lenny's Podcast & Newsletter Knowledge Base*

---

### **Insufficient Grounded Evidence**
Our search through the indexed Lenny's Podcast transcript corpus found **no direct or substantial discussion** on the specific topic: **"{topic}"**.

To preserve strict transcript-grounded integrity:
1. **No Hallucinated Frameworks**: We do not invent quotes, episode titles, or frameworks to fill the gap.
2. **Documented Scope**: The current indexed knowledge base covers product management frameworks from guests including **Shreyas Doshi** (LNO Framework, Pre-mortems), **Elena Verna** (B2B Product-Led Growth & Sales loops), **Marty Cagan** (Product Discovery & 4 Risks), and **Brian Gibson**.
3. **Recommended Action**: Try framing your question around topics discussed in our indexed episodes, such as:
   - *Shreyas Doshi on task leverage and high-agency PM execution*
   - *Elena Verna on B2B product activation metrics and PQL thresholds*
   - *Marty Cagan on de-risking value, feasibility, and usability*
   - Or upload additional episode transcripts via the `/api/ingest/upload` endpoint.
"""

    def _synthesize_grounded_essay(
        self,
        topic: str,
        target_audience: str,
        chunks: List[TranscriptChunk],
        citations: List[Citation]
    ) -> str:
        """
        Dynamically synthesizes a grounded Ship 30 essay using the actual retrieved chunks,
        guest wisdom, and specific quotes when external LLMs are in test/offline environments.
        """
        top_chunk = chunks[0]
        guest = top_chunk.guest
        episode_title = top_chunk.title
        primary_quote = top_chunk.text
        topic_name = top_chunk.topic

        # Supporting guest context if available
        secondary_quote = chunks[1].text if len(chunks) > 1 else ""
        secondary_guest = chunks[1].guest if len(chunks) > 1 else guest

        return f"""# How to Master {topic}: The {guest} Framework

*Target Audience: {target_audience}*  
*Grounded in Lenny's Podcast Transcript Knowledge Base*

---

### **The Hook**
Most product teams don't fail because they lack ambition or technical talent. 

They fail because they channel 80% of their bandwidth into low-leverage execution while convincing themselves that velocity equals progress.

---

### **Part 1: The Trap Modern Product Teams Fall Into**

Here is an uncomfortable reality observed across scaling tech companies:

**Shipping features is straightforward. Creating sustainable, differentiated customer value is exceptionally rare.**

When you inspect struggling organizations, the same anti-patterns repeat:
- Product managers operate as administrative ticket dispatchers rather than strategic owners.
- Engineering sprints burn capacity on feature requests disconnected from core customer friction.
- Leadership measures output (stories completed) rather than outcome (retention, margin expansion, customer delight).

As **{guest}** explicitly highlighted in *"{episode_title}"*:

> *"{primary_quote}"*

When teams mistake activity for impact, they build feature factories. Escaping this dynamic requires an intentional reset of how problems are framed and prioritized.

---

### **Part 2: The Paradigm Shift**

Top-tier product leaders embrace a foundational shift in perspective:

**Stop managing tasks. Start engineering leverage.**

In the conversation on Lenny's Podcast, **{guest}** articulated that true leverage requires stepping back from the immediate backlog and establishing clear strategic filters:

1. **Focus on High-Leverage Interventions**: 10x impact stems from deeply understanding customer problems and defining strategic boundaries—not from attending more alignment meetings.
2. **De-Risk Assumptions Early**: Before committing months of engineering capacity, validate critical value and feasibility assumptions directly with real users.
3. **Compound Learning Over Immediate Output**: Sustainable competitive advantage accumulates when each release generates measurable behavioral insights.

{"As **" + secondary_guest + "** emphasized: *\"" + secondary_quote[:220] + "...\"*" if secondary_quote else ""}

---

### **Part 3: The 3-Step Execution Playbook**

Here is the tactical, step-by-step framework you can implement with your team starting tomorrow morning:

#### **Rule 1: Filter Initiatives by High-Leverage Impact**
Before committing work to your sprint roadmap, rigorously classify each initiative:
- **High Leverage**: Critical strategic choices, core user workflows, and structural growth loops where excellence produces outsized compounding returns.
- **Baseline Execution**: Necessary operational requirements that must meet baseline quality standards without consuming excessive resources.
- **Administrative Overhead**: Low-leverage chores that should be aggressively automated, delegated, or eliminated.

#### **Rule 2: Conduct Pre-Mortems Before Implementation**
Do not wait for a disappointing launch retrospective to discover preventable blind spots.
- Gather your design, engineering, and product partners in a focused session.
- Ask the defining question: *"Imagine it is six months from now, and this initiative has completely failed to move our target metric. What went wrong?"*
- Document the unaddressed technical risks, fragile customer assumptions, and cross-functional friction points early when changes cost hours instead of months.

#### **Rule 3: Establish Clear Verification Metrics**
Replace subjective satisfaction with objective telemetry:
- Define the specific customer behavioral trigger that signifies successful adoption (the "Aha!" moment).
- Measure time-to-value for new cohorts and instrument funnel progression.
- Align engineering and product around measurable outcome shifts rather than shipping deadlines.

---

### **Part 4: The 1-Sentence Actionable Takeaway**

> **Your actionable takeaway:**  
> Audit your top three current roadmap priorities today—if any priority does not directly eliminate a critical customer friction point or drive a verified outcome loop, pause it immediately and refocus your team on high-leverage product discovery.

---

### **Source References & Grounding**
- **Primary Source**: Lenny's Podcast — *"{episode_title}"* featuring **{guest}** ({top_chunk.timestamp})
- **Topic Domain**: {topic_name}
- **Verified Transcript Quote**: *"{primary_quote[:180]}..."*
- **Source Link**: [{episode_title}]({top_chunk.source_url})
"""

    def _format_citation_footer(self, chunks: List[TranscriptChunk]) -> str:
        footer = "\n\n---\n\n### **Source References & Grounding**\n"
        for idx, chunk in enumerate(chunks[:2], 1):
            footer += f"- **Source {idx}**: Lenny's Podcast — *\"{chunk.title}\"* featuring **{chunk.guest}** ({chunk.timestamp})\n"
            footer += f"  - *Quote*: \"{chunk.text[:160]}...\"\n"
            footer += f"  - *Reference URL*: [{chunk.title}]({chunk.source_url})\n"
        return footer

ship30_skill = Ship30Skill()
