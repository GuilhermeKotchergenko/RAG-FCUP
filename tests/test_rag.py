"""
tests/test_rag.py

Integration-style test for the RAG pipeline using mock data.
Requires Qdrant and Ollama running locally.
Skip with: pytest tests/test_rag.py --ignore=tests/test_rag.py
or: pytest -m "not integration"
"""

import pytest

pytestmark = pytest.mark.integration  # skip by default: pytest -m "not integration"


@pytest.fixture(scope="module", autouse=True)
def env_setup(monkeypatch_module):
    monkeypatch_module.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch_module.setenv("QDRANT_COLLECTION", "fcup_test")
    monkeypatch_module.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch_module.setenv("LLM_MODEL", "llama3.1:8b")
    monkeypatch_module.setenv("EMBED_MODEL", "nomic-embed-text")


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped monkeypatch."""
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


def test_rag_query_returns_response_with_source(tmp_path):
    """
    Index 2 mock documents, query, and assert we get a response with source nodes.
    Requires live Qdrant + Ollama.
    """
    import json
    from scraper.ingest import run_ingest

    # Write 2 mock raw documents
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    for i, (url, text) in enumerate([
        ("https://sigarra.up.pt/fcup/pt/web_page.inicial", "O SIGARRA é o sistema de gestão académica da FCUP."),
        ("https://infociencias.fc.up.pt/", "O InfoCiências é o portal de informação da Faculdade de Ciências."),
    ]):
        doc = {"url": url, "title": f"Página {i+1}", "text": text, "crawled_at": "2024-01-01T00:00:00Z"}
        (raw_dir / f"doc{i}.json").write_text(json.dumps(doc))

    # Ingest into test collection
    run_ingest(raw_dir, "fcup_test")

    # Query
    from rag.pipeline import get_query_engine, format_sources
    import importlib, rag.pipeline as pipeline_module
    pipeline_module.get_query_engine.cache_clear()

    engine = get_query_engine()
    response = engine.query("O que é o SIGARRA?")

    assert response.response  # non-empty answer
    sources = format_sources(response.source_nodes)
    assert "sigarra.up.pt" in sources or "infociencias" in sources
