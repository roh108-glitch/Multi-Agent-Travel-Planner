import sys
import asyncio
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastmcp import FastMCP
from playwright.async_api import Page, Response, async_playwright

mcp = FastMCP(name="Accommodation")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Inline stealth script to mask automation flags
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
"""


def _build_search_url(
    location: str,
    checkin: str,
    checkout: str,
    guests: int = 2,
    rooms: int = 1,
    currency: str = "INR",
) -> str:
    """Builds search URL without rigid parameter filters to ensure reliable DOM rendering."""
    params = {
        "ss": location,
        "checkin": checkin,
        "checkout": checkout,
        "group_adults": guests,
        "no_rooms": rooms,
        "selected_currency": currency.upper(),
        "lang": "en-us",
    }
    return f"https://www.booking.com/searchresults.html?{urlencode(params)}"


async def _route_interceptor(route) -> None:
    """Blocks heavy static assets to speed up page load times."""
    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()


def _parse_price_value(price_str: str) -> Optional[float]:
    """Extracts the primary numeric price value from strings like '$150' or 'US$ 1,200 + taxes'."""
    try:
        # Match the first valid numeric cluster (including commas and decimals)
        match = re.search(r"[\d,]+(?:\.\d+)?", price_str)
        if match:
            cleaned = match.group(0).replace(",", "")
            return float(cleaned)
        return None
    except Exception:
        return None


def _compact_accommodation_data(
    raw_hotels: List[Dict[str, Any]],
    max_results: int = 8,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
) -> List[Dict[str, Any]]:
    compacted = []
    for item in raw_hotels:
        raw_price = str(item.get("price", "N/A")).strip()
        parsed_price = _parse_price_value(raw_price)

        # Apply budget post-filtering if price was successfully parsed
        if parsed_price is not None:
            if min_price is not None and parsed_price < min_price:
                continue
            if max_price is not None and parsed_price > max_price:
                continue

        compacted.append(
            {
                "name": str(item.get("name", "")).strip()[:60],
                "price": raw_price,
                "rating": str(item.get("rating", "N/A")).strip()[:11],
                "location": str(item.get("location", "N/A")).strip()[:40],
                "url": str(item.get("url", "")).split("?")[0],
            }
        )

        if len(compacted) >= max_results:
            break

    return compacted


async def _extract_dom_fallback(
    page: Page, max_results: int = 20
) -> List[Dict[str, Any]]:
    listings: List[Dict[str, Any]] = []
    try:
        cards = await page.locator("div[data-testid='property-card']").all()

        for card in cards[:max_results]:
            try:
                name_el = card.locator("div[data-testid='title']")
                price_el = card.locator(
                    "span[data-testid='price-and-discounted-price']"
                )
                rating_el = card.locator("div[data-testid='review-score']")
                link_el = card.locator("a[data-testid='title-link']")

                name = (
                    await name_el.inner_text()
                    if await name_el.count() > 0
                    else ""
                )
                price = (
                    await price_el.inner_text()
                    if await price_el.count() > 0
                    else "N/A"
                )
                rating = (
                    await rating_el.inner_text()
                    if await rating_el.count() > 0
                    else "N/A"
                )
                url = (
                    await link_el.get_attribute("href")
                    if await link_el.count() > 0
                    else ""
                )

                if name:
                    listings.append(
                        {
                            "name": name,
                            "price": price,
                            "rating": re.sub(r"\s+", " ", rating),
                            "url": url,
                        }
                    )
            except Exception:
                continue
    except Exception as e:
        print(f"[DOM Fallback Error]: {e}", file=sys.stderr)

    return listings


@mcp.tool()
async def fetch_accommodations(
    location: str,
    checkin: str,
    checkout: str,
    guests: int = 2,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    currency: str = "INR",
    max_results: int = 8,
    timeout_ms: int = 25000,
) -> List[Dict[str, Any]]:
    """Executes browser hotel extraction by building query URLs and reading the rendered page DOM.

    Args:
        location: Target destination (e.g. "Gurugram, Haryana").
        checkin: Check-in date in YYYY-MM-DD format.
        checkout: Check-out date in YYYY-MM-DD format.
        guests: Number of adult guests.
        min_price: Minimum budget limit in the chosen currency.
        max_price: Maximum budget limit in the chosen currency.
        currency: Preferred currency code (e.g. "USD", "INR").
        max_results: Maximum number of accommodation results to return.
        timeout_ms: Maximum navigation wait time in milliseconds.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1280,720",
            ],
        )

        try:
            context = await browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 720},
                locale="en-US",
                timezone_id="Asia/Kolkata",
            )

            # Apply stealth evasion script
            await context.add_init_script(STEALTH_JS)

            page = await context.new_page()

            # Block heavy static assets
            await page.route("**/*", _route_interceptor)

            # Build URL and navigate
            target_url = _build_search_url(
                location=location,
                checkin=checkin,
                checkout=checkout,
                guests=guests,
                currency=currency,
            )

            try:
                await page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                await page.wait_for_timeout(2500)
            except Exception as err:
                print(f"[Navigation Warning]: {err}. Triggering fallback...", file=sys.stderr)

            # Extract higher initial candidate count to account for budget filtering
            raw_hotels = await _extract_dom_fallback(
                page, max_results=max_results * 3
            )

            return _compact_accommodation_data(
                raw_hotels,
                max_results=max_results,
                min_price=min_price,
                max_price=max_price,
            )
        finally:
            await browser.close()





# async def main() -> None:
#     results = await fetch_accommodations(
#         location="laxman jhula",
#         checkin="2026-10-01",
#         checkout="2026-10-05",
#         guests=2,
#         min_price=1000,
#         max_price=10000,
#         currency="INR",
#         max_results=5,
#     )
#     print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    # asyncio.run(main())
    mcp.run(transport="stdio")
