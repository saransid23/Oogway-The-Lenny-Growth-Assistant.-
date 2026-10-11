import pytest
from app.rag.knowledge_base import KnowledgeBase
from app.rag.retriever import TranscriptRetriever

def test_knowledge_base_loading():
    kb = KnowledgeBase(data_dir="data/transcripts")
    assert len(kb.chunks) > 0, "Knowledge base should load transcript chunks"

def test_retriever_search_shreyas():
    kb = KnowledgeBase(data_dir="data/transcripts")
    retriever = TranscriptRetriever(kb=kb)
    chunks, citations = retriever.search("LNO framework Shreyas Doshi")
    assert len(chunks) > 0, "Should retrieve chunks for Shreyas Doshi LNO framework"
    assert "Shreyas Doshi" in citations[0].guest or "LNO" in citations[0].topic

def test_retriever_search_elena():
    kb = KnowledgeBase(data_dir="data/transcripts")
    retriever = TranscriptRetriever(kb=kb)
    chunks, citations = retriever.search("Product-Led Growth PLG Elena Verna")
    assert len(chunks) > 0, "Should retrieve chunks for Elena Verna PLG"
    assert "Elena Verna" in citations[0].guest
