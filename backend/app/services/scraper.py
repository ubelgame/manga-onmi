"""
Scraper adapters. Each adapter implements two async methods:
  - get_chapter_image_urls(chapter_url) -> list[str]
Playwright is used as fallback for unknown sites.
"""
import re
import httpx
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from app.services.storage import upload_image_bytes
import structlog

log = structlog.get_logger()


class MangaDexScraper:
    """Uses the public MangaDex API — no Playwright needed."""

    async def get_chapter_image_urls(self, chapter_url: str) -> list[str]:
        # Extract chapter UUID from URL like:
        # https://mangadex.org/chapter/abc-123-def/1
        match = re.search(r"chapter/([a-f0-9-]{36})", chapter_url)
        if not match:
            raise ValueError(f"Could not parse MangaDex chapter ID from: {chapter_url}")
        chapter_id = match.group(1)

        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://api.mangadex.org/at-home/server/{chapter_id}",
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()

        base = data["baseUrl"]
        h = data["chapter"]["hash"]
        return [f"{base}/data/{h}/{f}" for f in data["chapter"]["data"]]


class GenericScraper:
    """
    Playwright-based scraper for sites without a public API.
    Heuristic: grabs the largest images on the page that are
    sequential and likely manga page rasters.
    """

    SKIP_KEYWORDS = ["logo", "icon", "banner", "ad", "avatar", "thumb", "button"]

    async def get_chapter_image_urls(self, chapter_url: str) -> list[str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=["--no-sandbox"])
            page = await browser.new_page()
            await page.goto(chapter_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)  # let lazy-load settle

            # Collect all img src attributes
            img_elements = await page.query_selector_all("img")
            urls = []
            for el in img_elements:
                src = await el.get_attribute("src") or await el.get_attribute("data-src") or ""
                if src and not any(kw in src.lower() for kw in self.SKIP_KEYWORDS):
                    urls.append(src)

            await browser.close()
        return self._deduplicate(urls)

    def _deduplicate(self, urls: list[str]) -> list[str]:
        seen = set()
        result = []
        for u in urls:
            if u not in seen and (u.endswith(".jpg") or u.endswith(".png") or u.endswith(".webp")):
                seen.add(u)
                result.append(u)
        return result


def resolve_scraper(url: str):
    domain = urlparse(url).netloc
    if "mangadex.org" in domain:
        return MangaDexScraper()
    return GenericScraper()


async def scrape_and_store_chapter(chapter_url: str) -> list[dict]:
    """
    Downloads all page images for a chapter, uploads to S3,
    returns list of {page_number, s3_key, source_url}.
    """
    scraper = resolve_scraper(chapter_url)
    image_urls = await scraper.get_chapter_image_urls(chapter_url)
    log.info("Scraped image URLs", count=len(image_urls), url=chapter_url)

    results = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for i, img_url in enumerate(image_urls):
            try:
                r = await client.get(img_url, headers={"Referer": chapter_url})
                r.raise_for_status()
                key = upload_image_bytes(r.content, prefix="raw")
                results.append({"page_number": i, "s3_key": key, "source_url": img_url})
                log.info("Stored page", page=i, key=key)
            except Exception as e:
                log.error("Failed to download image", url=img_url, error=str(e))
    return results
