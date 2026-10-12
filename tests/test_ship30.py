import pytest
from app.skills.ship30 import ship30_skill

@pytest.mark.asyncio
async def test_two_different_topics_produce_different_essays():
    """Requirement: Two different topics produce appropriately different essays."""
    essay_1, citations_1 = await ship30_skill.generate_essay("Shreyas Doshi LNO framework")
    essay_2, citations_2 = await ship30_skill.generate_essay("Elena Verna Product-Led Growth loops")

    assert essay_1 != essay_2, "Two distinct topics must produce different essays"
    assert "Shreyas Doshi" in essay_1 or "LNO" in essay_1
    assert "Elena Verna" in essay_2 or "Product-Led" in essay_2

@pytest.mark.asyncio
async def test_retrieved_source_references_preserved():
    """Requirement: Retrieved source references are preserved in the essay."""
    essay, citations = await ship30_skill.generate_essay("Shreyas Doshi LNO framework")
    assert len(citations) > 0, "Citations must be returned"
    assert "Source References & Grounding" in essay
    assert citations[0].guest in essay

@pytest.mark.asyncio
async def test_insufficient_evidence_handled_gracefully():
    """Requirement: Insufficient evidence is handled gracefully without inventing facts."""
    unsupported_topic = "Quantum Computing Cryogenic Dilution Refrigerator Thermodynamics"
    essay, citations = await ship30_skill.generate_essay(unsupported_topic)

    assert "Insufficient Grounded Evidence" in essay or "Limitation Notice" in essay
    assert "Quantum Computing" in essay
    assert len(citations) == 0

def test_word_count_validation_flexibility():
    """Requirement: Word-count validation works without requiring exactly 1,250 words."""
    short_draft = "This is a brief summary of a framework without enough depth."
    validation_short = ship30_skill.validate_essay(short_draft, "LNO Framework")
    # Even if valid flag evaluates components, word_count is measured accurately
    assert validation_short["word_count"] == len(short_draft.split())

    # Rich essay with around 400-1400 words
    rich_essay = """# How to Master LNO Framework: The Shreyas Doshi Playbook
### The Hook
Most product teams fail because they spend 80% of energy on low leverage execution.
### Part 1: The Trap
Teams fall into feature factories and administrative overload.
### Part 2: The Paradigm Shift
Stop managing tasks. Start engineering leverage.
### Part 3: The 3-Step Execution Playbook
Rule 1: Categorize by Leverage.
Rule 2: Conduct Pre-Mortems.
Rule 3: Establish clear metrics.
### Part 4: The 1-Sentence Takeaway
Audit your top three initiatives today.
### Source References & Grounding
- Guest: Shreyas Doshi on Lenny's Podcast
"""
    validation_rich = ship30_skill.validate_essay(rich_essay, "LNO Framework")
    assert validation_rich["valid"] is True
    assert validation_rich["word_count"] > 50
    assert validation_rich["has_hook"] is True
    assert validation_rich["has_takeaway"] is True
