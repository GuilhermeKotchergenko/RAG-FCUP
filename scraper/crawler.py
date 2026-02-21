"""
scraper/crawler.py

Crawls a list of seed URLs from SIGARRA and InfoCiências, respecting
the robots.txt rules (Crawl-delay: 3s, blocked paths).

Each page is saved to data/raw/<slug>.json with keys:
  - url:       source URL
  - title:     page <title>
  - text:      cleaned plain text
  - crawled_at: ISO timestamp

Usage:
    python scraper/crawler.py
    python scraper/crawler.py --limit 5   # Only crawl the first 5 URLs
"""

import asyncio
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# ── Configuration ──────────────────────────────────────────────────────────────

RAW_DATA_DIR = Path("data/raw")
SEED_URL_FILE = Path("data/seed_urls.txt")
CRAWL_DELAY_SECONDS = 3  # robots.txt compliance

# Paths blocked by robots.txt
BLOCKED_PATTERNS = [
    r"/Shibboleth\.sso/",
    r"horarios_geral",
    r"/validar",
]

# Initial seed URLs
DEFAULT_SEEDS = [
    "https://sigarra.up.pt/fcup/pt/web_page.inicial",
    "https://info.fc.up.pt/fcup/static/index.php?f_id=641",
]

HEADERS = {
    "User-Agent": "RAG-FCUP-Bot/1.0 (academic project; respects robots.txt)",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
}

# ── Helpers ───────────────────────────────────────────────────────────────────


def is_blocked(url: str) -> bool:
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def url_to_slug(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Remove scripts, styles, nav, footer
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Collapse whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    return title_tag.get_text(strip=True) if title_tag else "Sem título"


def load_seeds() -> list[str]:
    if SEED_URL_FILE.exists():
        return [
            line.strip()
            for line in SEED_URL_FILE.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    return DEFAULT_SEEDS


# ── Crawler ───────────────────────────────────────────────────────────────────


async def crawl(urls: list[str], limit: int | None = None) -> list[dict]:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    visited = set()
    targets = urls[:limit] if limit else urls

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        for i, url in enumerate(targets):
            if url in visited:
                continue
            if is_blocked(url):
                print(f"[crawler] ⛔ Blocked by robots.txt: {url}")
                continue

            visited.add(url)
            print(f"[crawler] [{i+1}/{len(targets)}] Crawling: {url}")

            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except Exception as exc:
                print(f"[crawler] ⚠️  Failed to fetch {url}: {exc}")
                continue

            title = extract_title(resp.text)
            text = extract_text(resp.text)

            record = {
                "url": url,
                "title": title,
                "text": text,
                "crawled_at": datetime.now(UTC).isoformat(),
            }

            slug = url_to_slug(url)
            out_path = RAW_DATA_DIR / f"{slug}.json"
            out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
            print(f"[crawler] ✅ Saved {len(text)} chars → {out_path}")
            results.append(record)

            if i < len(targets) - 1:
                print(f"[crawler] 💤 Waiting {CRAWL_DELAY_SECONDS}s (robots.txt compliance)...")
                await asyncio.sleep(CRAWL_DELAY_SECONDS)

    print(f"\n[crawler] Done. {len(results)}/{len(targets)} pages crawled.")
    return results


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FCUP RAG Crawler")
    parser.add_argument("--limit", type=int, default=None, help="Max pages to crawl")
    parser.add_argument(
        "--urls",
        nargs="+",
        default=None,
        help="Explicit URLs to crawl (overrides seed file)",
    )
    args = parser.parse_args()

    seeds = args.urls if args.urls else load_seeds()
    asyncio.run(crawl(seeds, limit=args.limit))
