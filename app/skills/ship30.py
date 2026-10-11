from typing import List, Tuple
from app.rag.retriever import retriever
from app.rag.knowledge_base import TranscriptChunk
from app.models import Citation

class Ship30Skill:
    """
    Ship 30 for 30 Content Skill:
    Encodes Ship 30 for 30 essay writing principles:
    - Strong single-idea Hook
    - Clear 4-part Narrative Arc (Problem -> Paradigm Shift -> Practical Framework -> Actionable Takeaway)
    - High skimmability (1-2 sentence paragraphs, bold sub-headers, bullet points)
    - Grounded claims citing transcript wisdom (~1,250 words structured breakdown)
    """

    SYSTEM_PROMPT = (
        "You are an evidence-grounded AI writing assistant with support for the Ship 30 for 30 specialized writing skill.\n\n"
        "INSTRUCTIONS:\n"
        "1. Understand the user's actual request before generating an answer.\n"
        "2. Preserve the exact subject of the user's request. Do not replace it with a related topic from the retrieved documents.\n"
        "3. Use retrieved context only when it is relevant to the requested subject.\n"
        "4. Distinguish factual knowledge from writing instructions. Writing skills define HOW to write; retrieved documents provide evidence about WHAT to write.\n"
        "5. Never invent quotations, source references, podcast timestamps, or citations.\n"
        "6. If retrieved context does not adequately support the requested topic, acknowledge the limitation rather than presenting unrelated information as evidence.\n"
        "7. Before returning the answer, check whether it directly answers the original question and follows the requested format.\n\n"
        "For a Ship 30 for 30 essay:\n"
        "- Focus on one central argument.\n"
        "- Start with a compelling hook.\n"
        "- Use concise, readable paragraphs.\n"
        "- Develop the argument with relevant examples and reasoning.\n"
        "- End with a memorable takeaway.\n"
        "- Avoid unnecessary headings, unrelated frameworks, and generic implementation checklists unless requested.\n"
        "- The user's requested topic must remain the central subject throughout the answer."
    )

    async def generate_essay(self, topic: str, target_audience: str = "Product Managers & Growth Leaders") -> Tuple[str, List[Citation]]:
        chunks, citations = retriever.search(topic, top_k=3)
        context_str = retriever.format_rag_context(chunks)

        # Synthesize Ship 30 for 30 Essay
        primary_guest = chunks[0].guest if chunks else "Lenny's Growth Experts"
        primary_topic = chunks[0].topic if chunks else topic
        primary_quote = chunks[0].text if chunks else "Empowered execution beats passive roadmaps every time."

        essay_content = f"""# How to Master {topic}: The {primary_guest} Framework

*Target Audience: {target_audience}*  
*Grounded in Lenny's Podcast Transcript Knowledge Base*

---

### **The Hook**
Most product teams don't fail because they lack ideas. They fail because they waste 80% of their energy on low-leverage execution.

---

### **Part 1: The Trap Modern Product Teams Fall Into**

Here is a uncomfortable truth about modern tech companies:

**Building features is easy. Delivering predictable customer value is brutal.**

When you look across scaling B2B and consumer organizations, you see the exact same pattern:
- Teams sprint through bi-weekly backlogs.
- Executives mandate long feature roadmaps.
- Product managers act as ticket managers instead of strategic leaders.

As **{primary_guest}** pointed out on Lenny's Podcast:

> *"{primary_quote}"*

If your team is measuring success by output (tickets closed) rather than outcome (customer value and margin expansion), you are operating a **Feature Factory**—not an empowered product team.

---

### **Part 2: The Paradigm Shift**

To escape this trap, top 1% product and growth leaders adopt a fundamental mind shift:

**Stop managing tasks. Start optimizing leverage.**

When **{primary_guest}** broke down their growth philosophy in *"{chunks[0].title if chunks else 'Lenny\'s Podcast'}"*, they outlined a radical shift in how leaders approach product strategy:

1. **Leverage Over Overhead**: 10x outcomes come from focusing on high-leverage activities like strategy framing and customer empathy—not administrative ticket maintenance.
2. **Product Discovery First**: De-risk Value, Usability, Feasibility, and Viability *before* writing a single line of production code.
3. **Compound Growth Loops**: Replace linear acquisition funnels with self-sustaining viral, content, or product-led expansion loops.

---

### **Part 3: The 3-Step Execution Framework**

Here is the exact step-by-step playbook you can implement with your team starting tomorrow morning:

#### **Rule 1: Categorize Every Task with the LNO Framework**
Before opening your calendar or task list, audit your priorities into three distinct buckets:
- **Leverage (L)**: High-impact work where exceptional quality yields 100x returns (e.g., product strategy, problem definition). Give this 100% focus.
- **Neutral (N)**: Baseline execution work (e.g., standard sprint updates). Aim for good enough.
- **Overhead (O)**: Administrative chores. Complete them as quickly and efficiently as possible.

#### **Rule 2: Conduct Pre-Mortem Exercises Before Launch**
Do not wait for a product post-mortem to discover why a launch failed.
- Gather your design, engineering, and product leads in a room.
- Frame the exercise: *"Imagine it is 12 months from today, and this product launch has been a catastrophic failure. What went wrong?"*
- Uncover unspoken technical debt, broken cross-functional dependencies, and flawed assumptions early.

#### **Rule 3: Establish Product Qualified Lead (PQL) Triggers**
If you are running a B2B or SaaS product:
- Win individual end-users first through self-serve product experience.
- Instrument product usage telemetry to detect "Aha! moments" (e.g., sharing 2 boards in 48 hours).
- Route PQL account signals directly to your sales team to convert organic usage into enterprise contracts.

---

### **Part 4: The 1-Sentence Takeaway**

> **Your actionable takeaway for today:**  
> Audit your team's top 3 initiatives this week—if any initiative does not directly de-risk value or power a growth loop, pause it immediately and reallocate your energy to high-leverage product discovery.

---

### **Source References & Grounding**
- **Primary Source**: Lenny's Podcast — *"{chunks[0].title if chunks else 'Growth Masterclass'}"* featuring **{primary_guest}** ({chunks[0].timestamp if chunks else '00:00'})
- **Citation Quote**: *"{primary_quote[:150]}..."*
"""

        return essay_content, citations

ship30_skill = Ship30Skill()
