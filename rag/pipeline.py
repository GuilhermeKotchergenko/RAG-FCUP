"""
rag/pipeline.py

LlamaIndex RAG pipeline connecting LlamaIndex ↔ Qdrant ↔ Ollama.

Usage:
    from rag.pipeline import get_query_engine, query

    engine = get_query_engine()
    response = await query("Como me inscrevo em cadeiras no SIGARRA?")
    print(response.response)
    print(response.source_nodes)
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient

from rag.prompts import QA_TEMPLATE, REFINE_TEMPLATE

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "fcup_docs")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# How many chunks to retrieve
TOP_K = 5
# Minimum similarity threshold (cosine, 0–1)
SIMILARITY_CUTOFF = 0.3


# ── Setup ──────────────────────────────────────────────────────────────────────


def configure_settings() -> None:
    """Set global LlamaIndex settings (called once at startup)."""
    Settings.llm = Ollama(
        model=LLM_MODEL,
        base_url=OLLAMA_BASE_URL,
        request_timeout=120.0,
        is_function_calling_model=False,
    )
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )


def _build_index():
    configure_settings()
    client = QdrantClient(url=QDRANT_URL)
    aclient = AsyncQdrantClient(url=QDRANT_URL)
    vector_store = QdrantVectorStore(
        client=client,
        aclient=aclient,
        collection_name=COLLECTION,
    )
    return VectorStoreIndex.from_vector_store(vector_store)


@lru_cache(maxsize=1)
def get_query_engine() -> RetrieverQueryEngine:
    """
    Non-streaming query engine — for CLI testing and pytest.
    Returns a Response with .response and .source_nodes.
    """
    index = _build_index()
    retriever = index.as_retriever(similarity_top_k=TOP_K)
    response_synthesizer = get_response_synthesizer(
        response_mode="compact",
        text_qa_template=QA_TEMPLATE,
        refine_template=REFINE_TEMPLATE,
        streaming=False,
    )
    postprocessors = [SimilarityPostprocessor(similarity_cutoff=SIMILARITY_CUTOFF)]
    return RetrieverQueryEngine(
        retriever=retriever,
        response_synthesizer=response_synthesizer,
        node_postprocessors=postprocessors,
    )


@lru_cache(maxsize=1)
def get_streaming_query_engine() -> RetrieverQueryEngine:
    """
    Streaming query engine — for Chainlit (token-by-token via async_response_gen).
    """
    index = _build_index()
    retriever = index.as_retriever(similarity_top_k=TOP_K)
    response_synthesizer = get_response_synthesizer(
        response_mode="compact",
        text_qa_template=QA_TEMPLATE,
        refine_template=REFINE_TEMPLATE,
        streaming=True,
    )
    postprocessors = [SimilarityPostprocessor(similarity_cutoff=SIMILARITY_CUTOFF)]
    return RetrieverQueryEngine(
        retriever=retriever,
        response_synthesizer=response_synthesizer,
        node_postprocessors=postprocessors,
    )


def query(question: str) -> object:
    """
    Synchronous helper for quick CLI testing.
    Returns a LlamaIndex Response with .response and .source_nodes.
    """
    engine = get_query_engine()
    return engine.query(question)


def format_sources(source_nodes: list) -> str:
    """Return a markdown-formatted source list from retrieved nodes."""
    seen = set()
    lines = []
    for node in source_nodes:
        url = node.metadata.get("url") or node.metadata.get("source", "")
        title = node.metadata.get("title", url)
        if url and url not in seen:
            seen.add(url)
            lines.append(f"- [{title}]({url})")
    return "\n".join(lines) if lines else ""


if __name__ == "__main__":
    import sys

    question = " ".join(sys.argv[1:]) or "O que é o SIGARRA?"
    print(f"[RAG] Query: {question}\n")
    response = query(question)
    print(response.response)
    sources = format_sources(response.source_nodes)
    if sources:
        print(f"\n📚 Fontes:\n{sources}")
