"""
tests/test_scraper.py

Unit tests for the crawler: robots.txt compliance, URL blocking, text extraction.
"""

import json
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch


# ── is_blocked ────────────────────────────────────────────────────────────────


def test_blocked_shibboleth():
    from scraper.crawler import is_blocked
    assert is_blocked("https://sigarra.up.pt/Shibboleth.sso/Login") is True


def test_blocked_horarios():
    from scraper.crawler import is_blocked
    assert is_blocked("https://sigarra.up.pt/fcup/pt/horarios_geral.lista") is True


def test_allowed_url():
    from scraper.crawler import is_blocked
    assert is_blocked("https://sigarra.up.pt/fcup/pt/web_page.inicial") is False


def test_allowed_infociencias():
    from scraper.crawler import is_blocked
    assert is_blocked("https://infociencias.fc.up.pt/") is False


# ── extract_text ──────────────────────────────────────────────────────────────


def test_extract_text_removes_scripts():
    from scraper.crawler import extract_text
    html = "<html><body><script>alert(1)</script><p>Olá FCUP</p></body></html>"
    text = extract_text(html)
    assert "alert" not in text
    assert "Olá FCUP" in text


def test_extract_title():
    from scraper.crawler import extract_title
    html = "<html><head><title>SIGARRA - FCUP</title></head><body></body></html>"
    assert extract_title(html) == "SIGARRA - FCUP"


def test_extract_title_fallback():
    from scraper.crawler import extract_title
    html = "<html><body><p>No title here</p></body></html>"
    assert extract_title(html) == "Sem título"


# ── url_to_slug ───────────────────────────────────────────────────────────────


def test_slug_is_deterministic():
    from scraper.crawler import url_to_slug
    assert url_to_slug("https://example.com") == url_to_slug("https://example.com")


def test_different_urls_different_slugs():
    from scraper.crawler import url_to_slug
    assert url_to_slug("https://a.com") != url_to_slug("https://b.com")


# ── load_seeds ────────────────────────────────────────────────────────────────


def test_load_seeds_default(tmp_path, monkeypatch):
    """When no seed file exists, should return the default seed list."""
    monkeypatch.chdir(tmp_path)
    from scraper import crawler
    monkeypatch.setattr(crawler, "SEED_URL_FILE", tmp_path / "nonexistent.txt")
    seeds = crawler.load_seeds()
    assert len(seeds) >= 2
    assert any("sigarra" in s for s in seeds)
    assert any("infociencias" in s for s in seeds)


def test_load_seeds_from_file(tmp_path, monkeypatch):
    seed_file = tmp_path / "seeds.txt"
    seed_file.write_text("https://example.com/a\nhttps://example.com/b\n# comment\n")
    monkeypatch.chdir(tmp_path)
    from scraper import crawler
    monkeypatch.setattr(crawler, "SEED_URL_FILE", seed_file)
    seeds = crawler.load_seeds()
    assert seeds == ["https://example.com/a", "https://example.com/b"]
