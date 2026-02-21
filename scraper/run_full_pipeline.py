"""
scraper/run_full_pipeline.py

Convenience script: crawl → ingest in one command.

Usage:
    python scraper/run_full_pipeline.py
    python scraper/run_full_pipeline.py --limit 100   # crawl at most 100 pages
    python scraper/run_full_pipeline.py --skip-crawl  # only re-ingest existing raw data
"""

import argparse
import asyncio
from pathlib import Path

from scraper.crawler import crawl, load_seeds
from scraper.ingest import run_ingest

import os
from dotenv import load_dotenv

load_dotenv()

RAW_DATA_DIR = Path("data/raw")
COLLECTION = os.getenv("QDRANT_COLLECTION", "fcup_docs")


async def main(limit: int | None, skip_crawl: bool) -> None:
    if not skip_crawl:
        print("=" * 60)
        print("FASE 1 – CRAWL")
        print("=" * 60)
        seeds = load_seeds()
        print(f"Seeds: {seeds}\n")
        await crawl(seeds, limit=limit)
    else:
        print("[pipeline] --skip-crawl: using existing data/raw/ files.\n")

    print("\n" + "=" * 60)
    print("FASE 2 – INGEST → QDRANT")
    print("=" * 60)
    run_ingest(RAW_DATA_DIR, COLLECTION)
    print("\n✅ Pipeline completo!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full RAG pipeline: crawl + ingest")
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Max pages to crawl (default: 500)",
    )
    parser.add_argument(
        "--skip-crawl",
        action="store_true",
        help="Skip crawling and only re-ingest existing raw data",
    )
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.skip_crawl))
