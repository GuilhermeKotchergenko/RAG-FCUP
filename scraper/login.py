"""
scraper/login.py

Opens the SIGARRA FCUP login page in a headed Playwright browser,
waits for you to log in manually, then saves the browser auth state
to browser_state.json for use by the crawler.

Usage:
    python scraper/login.py
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

STATE_FILE = Path("data/browser_state.json")
SIGARRA_LOGIN_URL = "https://sigarra.up.pt/fcup/pt/IDENTIFICACAO.ENTRADA_WEB"


async def main() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"[login] Opening SIGARRA login page: {SIGARRA_LOGIN_URL}")
        await page.goto(SIGARRA_LOGIN_URL)

        print("[login] Please log in manually in the browser window.")
        print("[login] Waiting for navigation to the authenticated area...")

        # Wait until the URL no longer contains the login path
        await page.wait_for_url(
            lambda url: "IDENTIFICACAO.ENTRADA_WEB" not in url,
            timeout=120_000,  # 2 minutes for manual login
        )

        print("[login] Login detected! Saving browser state...")
        await context.storage_state(path=str(STATE_FILE))

        print(f"[login] ✅ State saved to {STATE_FILE}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
