"""
scraper/crawler.py

Recursive BFS crawler for SIGARRA FCUP and InfoCiências.
Starts from seed URLs, extracts all links within the allowed domains,
and follows them automatically – respecting robots.txt rules.

Each page is saved to data/raw/<slug>.json with keys:
  - url:        source URL
  - title:      page <title>
  - text:       cleaned plain text
  - crawled_at: ISO timestamp

Usage:
    python scraper/crawler.py                   # full crawl (all pages)
    python scraper/crawler.py --limit 50        # stop after 50 pages
    python scraper/crawler.py --no-recurse      # only crawl seed URLs (original behaviour)
"""

import asyncio
import hashlib
import json
import re
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# ── Configuration ──────────────────────────────────────────────────────────────

RAW_DATA_DIR = Path("data/raw")
SEED_URL_FILE = Path("data/seed_urls.txt")
CRAWL_DELAY_SECONDS = 3      # robots.txt crawl-delay compliance
MAX_PAGES_DEFAULT = 500      # safety cap to avoid infinite crawls

# Only follow links within these domain prefixes
ALLOWED_PREFIXES = [
    "https://sigarra.up.pt/fcup/",   # FCUP section of SIGARRA only
    "https://info.fc.up.pt/",        # entire InfoCiências portal
]

# Paths / patterns blocked by robots.txt or undesirable
BLOCKED_PATTERNS = [
    r"/Shibboleth\.sso/",
    r"horarios_geral",
    r"/validar",
    r"IDENTIFICACAO\.ENTRADA",       # login page
    r"logout",
    r"\.pdf$",                       # skip PDFs (binary, no text)
    r"\.jpg$", r"\.png$", r"\.gif$", r"\.css$", r"\.js$",
]

# Initial seed URLs (also loaded from data/seed_urls.txt if present)
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


def is_allowed(url: str) -> bool:
    """Only crawl URLs within the FCUP-relevant domains."""
    return any(url.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def normalise_url(url: str) -> str:
    """Strip fragments and trailing slashes for deduplication."""
    parsed = urlparse(url)
    # Drop the fragment (#...) and normalise
    clean = parsed._replace(fragment="").geturl()
    return clean.rstrip("/")


def url_to_slug(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    return title_tag.get_text(strip=True) if title_tag else "Sem título"


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract all <a href> links, resolve relative URLs, and filter."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        # Skip javascript/mailto/anchors
        if href.startswith(("javascript:", "mailto:", "#", "tel:")):
            continue
        absolute = urljoin(base_url, href)
        normed = normalise_url(absolute)
        if is_allowed(normed) and not is_blocked(normed):
            links.append(normed)
    return links


def load_seeds() -> list[str]:
    if SEED_URL_FILE.exists():
        return [
            line.strip()
            for line in SEED_URL_FILE.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    return DEFAULT_SEEDS


# ── Crawler ───────────────────────────────────────────────────────────────────


async def crawl(
    seeds: list[str],
    limit: int | None = MAX_PAGES_DEFAULT,
    recurse: bool = True,
) -> list[dict]:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    visited: set[str] = set()
    queue: deque[str] = deque(normalise_url(u) for u in seeds)
    results: list[dict] = []
    page_count = 0

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        while queue:
            if limit and page_count >= limit:
                print(f"\n[crawler] ⚠️  Page limit ({limit}) reached. Stopping.")
                break

            url = queue.popleft()

            if url in visited:
                continue
            if is_blocked(url):
                print(f"[crawler] ⛔ Blocked: {url}")
                continue
            if not is_allowed(url):
                continue

            visited.add(url)
            page_count += 1
            queued = len(queue)
            print(f"[crawler] [{page_count}{'/' + str(limit) if limit else ''}] "
                  f"(queue: {queued}) {url}")

            try:
                resp = await client.get(url)
                resp.raise_for_status()
                # Only process HTML responses
                content_type = resp.headers.get("content-type", "")
                if "text/html" not in content_type:
                    print(f"[crawler] ⏭️  Skipping non-HTML ({content_type[:30]}): {url}")
                    continue
            except Exception as exc:
                print(f"[crawler] ⚠️  Failed: {url} → {exc}")
                continue

            title = extract_title(resp.text)
            text = extract_text(resp.text)

            # Skip pages with very little text (login redirects, empty pages)
            if len(text) < 100:
                print(f"[crawler] ⏭️  Too little text ({len(text)} chars), skipping.")
                continue

            record = {
                "url": url,
                "title": title,
                "text": text,
                "crawled_at": datetime.now(UTC).isoformat(),
            }

            slug = url_to_slug(url)
            out_path = RAW_DATA_DIR / f"{slug}.json"
            out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
            print(f"[crawler] ✅ {title!r} — {len(text):,} chars → {out_path.name}")
            results.append(record)

            # Discover new links if recursive mode is on
            if recurse:
                new_links = extract_links(resp.text, url)
                added = 0
                for link in new_links:
                    if link not in visited and link not in queue:
                        queue.append(link)
                        added += 1
                if added:
                    print(f"[crawler]    ↳ {added} new links queued")

            print(f"[crawler] 💤 {CRAWL_DELAY_SECONDS}s pause...")
            await asyncio.sleep(CRAWL_DELAY_SECONDS)

    print(f"\n[crawler] ✅ Done. {len(results)} pages saved to {RAW_DATA_DIR}/")
    return results


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FCUP RAG Recursive Crawler")
    parser.add_argument(
        "--limit",
        type=int,
        default=MAX_PAGES_DEFAULT,
        help=f"Max pages to crawl (default: {MAX_PAGES_DEFAULT})",
    )
    parser.add_argument(
        "--no-recurse",
        action="store_true",
        help="Only crawl the seed URLs (no link following)",
    )
    parser.add_argument(
        "--urls",
        nargs="+",
        default=None,
        help="Override seed URLs from command line",
    )
    args = parser.parse_args()

    seeds = args.urls if args.urls else load_seeds()
    asyncio.run(crawl(seeds, limit=args.limit, recurse=not args.no_recurse))
