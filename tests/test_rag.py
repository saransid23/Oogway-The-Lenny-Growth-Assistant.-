import pytest
from app.rag.knowledge_base import KnowledgeBase
from app.rag.retriever import TranscriptRetriever

def test_knowledge_base_loading():
    kb = KnowledgeBase(data_dir="data/transcripts")
    assert len(kb.chunks) > 0, "Knowledge base should load transcript chunks"

def test_idempotent_duplicate_detection():
    """Requirement: Ingestion must be idempotent; rerunning does not duplicate chunks."""
    kb = KnowledgeBase(data_dir="data/transcripts")
    initial_count = len(kb.chunks)

    # Ingest the same files again
    stats = kb.load_transcripts()
    assert len(kb.chunks) == initial_count, "Chunk count must remain identical after reloading identical transcripts"
    assert stats["duplicates_skipped"] >= 0

def test_retriever_search_shreyas():
    kb = KnowledgeBase(data_dir="data/transcripts")
    retriever = TranscriptRetriever(kb=kb)
    chunks, citations = retriever.search("LNO framework Shreyas Doshi")
    assert len(chunks) > 0
    assert "Shreyas Doshi" in citations[0].guest or "LNO" in citations[0].topic
    assert citations[0].score > 0.08
    assert citations[0].timestamp != ""
    assert citations[0].source_url != ""

def test_retriever_search_elena():
    kb = KnowledgeBase(data_dir="data/transcripts")
    retriever = TranscriptRetriever(kb=kb)
    chunks, citations = retriever.search("Product-Led Growth PLG Elena Verna")
    assert len(chunks) > 0
    assert "Elena Verna" in citations[0].guest

def test_retriever_unsupported_question():
    """Requirement: Retrieval correctly identifies unsupported questions."""
    kb = KnowledgeBase(data_dir="data/transcripts")
    retriever = TranscriptRetriever(kb=kb)
    chunks, citations = retriever.search("Dark matter astrophysics gravitational waves", threshold=0.15)
    assert len(chunks) == 0
    assert len(citations) == 0

def test_retrieval_diagnostics():
    """Requirement: Diagnostics endpoint provides score breakdown for debugging."""
    kb = KnowledgeBase(data_dir="data/transcripts")
    retriever = TranscriptRetriever(kb=kb)
    diag = retriever.diagnose_query("Shreyas Doshi LNO", top_k=3)
    assert "query" in diag
    assert "query_terms" in diag
    assert "top_candidates" in diag
    assert len(diag["top_candidates"]) > 0
    assert "keyword_score" in diag["top_candidates"][0]
