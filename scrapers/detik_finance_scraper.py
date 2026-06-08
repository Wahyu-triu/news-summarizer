"""
detik_finance_scraper.py
------------------------
Scrapes articles from finance.detik.com by category.

Usage:
    python detik_finance_scraper.py --category finansial
    python detik_finance_scraper.py --category berita-ekonomi-bisnis --limit 10
    python detik_finance_scraper.py --category moneter --output results.json

Available categories (URL slugs):
    finansial               → Finansial / Perbankan
    berita-ekonomi-bisnis   → Ekonomi Bisnis
    infrastruktur           → Infrastruktur
    energi                  → Energi
    industri                → Industri
    fintech                 → Kripto / Fintech
    perencanaan-keuangan    → Perencanaan Keuangan
    moneter                 → Moneter
    loker                   → Loker
    bursa-dan-valas         → Bursa & Valas
    solusiukm               → UKM & Waralaba

Output fields per article:
    category, title, author, date_publish, content, date_scraped
"""

import argparse
import json
import time
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://finance.detik.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://finance.detik.com/",
}

REQUEST_DELAY = 1.5  # seconds between requests (be polite)

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_soup(url: str, session: requests.Session) -> BeautifulSoup:
    """Fetch a URL and return a BeautifulSoup object."""
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as exc:
        print(f"  [WARN] Failed to fetch {url}: {exc}", file=sys.stderr)
        return None


def normalize_category(category: str) -> str:
    """
    Accept human-readable names or URL slugs.
    e.g. 'financial' → 'finansial', 'business' → 'berita-ekonomi-bisnis'
    """
    aliases = {
        # English friendly aliases
        "financial":        "finansial",
        "finance":          "finansial",
        "banking":          "finansial",
        "business":         "berita-ekonomi-bisnis",
        "economy":          "berita-ekonomi-bisnis",
        "economics":        "berita-ekonomi-bisnis",
        "infrastructure":   "infrastruktur",
        "energy":           "energi",
        "industry":         "industri",
        "crypto":           "fintech",
        "fintech":          "fintech",
        "planning":         "perencanaan-keuangan",
        "monetary":         "moneter",
        "jobs":             "loker",
        "stock":            "bursa-dan-valas",
        "forex":            "bursa-dan-valas",
        "ukm":              "solusiukm",
        "smb":              "solusiukm",
        # Indonesian originals pass through unchanged
    }
    slug = category.strip().lower().replace(" ", "-")
    return aliases.get(slug, slug)


# ── Listing page ─────────────────────────────────────────────────────────────

def get_article_links(category_slug: str, limit: int, session: requests.Session) -> list[str]:
    """
    Scrape article links from the category listing page.
    Detik uses a News Feed section; links appear as <a href="..."> inside
    article/h3 tags on the listing page.
    """
    url = f"{BASE_URL}/{category_slug}"
    print(f"[*] Fetching listing: {url}")
    soup = get_soup(url, session)
    if not soup:
        return []

    seen = set()
    links = []

    # Primary: all <a> tags whose href matches a detik finance article pattern
    # Pattern: https://finance.detik.com/<section>/d-<id>/<slug>
    article_pattern = re.compile(
        r"https://finance\.detik\.com/[^/]+/d-\d+/[^\"'\s]+"
    )

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if article_pattern.match(href) and href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= limit:
            break

    print(f"[*] Found {len(links)} article links.")
    return links


# ── Article page ─────────────────────────────────────────────────────────────

def parse_article(url: str, category_slug: str, session: requests.Session) -> dict | None:
    """
    Fetch and parse a single article page.
    Returns a dict with: category, title, author, date_publish, content, date_scraped
    """
    soup = get_soup(url, session)
    if not soup:
        return None

    # ── title ──
    title = None
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"].strip() if og_title else "N/A"

    # ── author ──
    # Meta tag: <meta name="author" content="..."> or <meta name="dtk:author" ...>
    author = None
    for meta_name in ("author", "dtk:author"):
        tag = soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            author = tag["content"].strip()
            break
    if not author:
        # Fallback: look for author byline in page body
        byline = soup.find(class_=re.compile(r"author|byline|writer", re.I))
        author = byline.get_text(strip=True) if byline else "N/A"

    # ── date_publish ──
    date_publish = None

    # Meta: <meta name="dtk:publishdate" content="2026/06/05 20:30:23">
    for meta_name in ("publishdate", "dtk:publishdate", "createdate", "dtk:createddate"):
        tag = soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            raw = tag["content"].strip()
            try:
                # Format: "2026/06/05 20:30:23"
                date_publish = datetime.strptime(raw, "%Y/%m/%d %H:%M:%S").isoformat()
            except ValueError:
                date_publish = raw
            break

    if not date_publish:
        # Fallback: look for <time> element
        time_tag = soup.find("time")
        if time_tag:
            date_publish = time_tag.get("datetime") or time_tag.get_text(strip=True)

    if not date_publish:
        date_publish = "N/A"

    # ── content ──
    content = _extract_content(soup)

    # ── category ──
    # Use the breadcrumb on the page when available
    breadcrumb = soup.select("div.breadcrumb a, nav.breadcrumb a")
    if breadcrumb and len(breadcrumb) >= 2:
        category_label = breadcrumb[-1].get_text(strip=True)
    else:
        # Derive from URL path segment
        path_parts = url.replace(BASE_URL + "/", "").split("/")
        category_label = path_parts[0].replace("-", " ").title() if path_parts else category_slug

    return {
        "news_platform": "detik_finance",
        "category":     category_label,
        "title":        title,
        "author":       author,
        "date_publish": date_publish,
        "content":      content,
        "date_scraped": datetime.now(timezone.utc).isoformat(),
        "source_url":   url,
    }


def _extract_content(soup: BeautifulSoup) -> str:
    """
    Extract clean article body text.
    Detik wraps content in <div class="detail__body-text itp_bodycontent"> or similar.
    """
    # Try known content containers (most specific first)
    container_selectors = [
        "div.detail__body-text",
        "div.itp_bodycontent",
        "div[class*='body-text']",
        "article",
        "div.detail__body",
    ]

    body = None
    for sel in container_selectors:
        body = soup.select_one(sel)
        if body:
            break

    if not body:
        return "N/A"

    # Remove unwanted nested elements (ads, related links, tables, scripts)
    for tag in body.find_all(["script", "style", "ins", "iframe", "figure",
                               "table", "aside", "div[class*='ads']"]):
        tag.decompose()

    # Remove "Baca juga" (read also) inline boxes
    for tag in body.find_all(True):
        try:
            cls = " ".join(tag.get("class", []))
            if "ads" in cls.lower() or "baca-juga" in cls.lower() or "related" in cls.lower():
                tag.decompose()
        except Exception:
            continue

    # Collect paragraph text
    paragraphs = []
    for p in body.find_all(["p", "h2", "h3", "h4", "li"]):
        text = p.get_text(separator=" ", strip=True)
        # Skip very short strings (ads, noise) and "ADVERTISEMENT" banners
        if len(text) > 20 and "ADVERTISEMENT" not in text.upper():
            paragraphs.append(text)

    return "\n\n".join(paragraphs) if paragraphs else body.get_text(separator="\n", strip=True)


# ── Main ─────────────────────────────────────────────────────────────────────

def scrape(category: str, limit: int, output: str | None, delay: float):
    slug = normalize_category(category)
    print(f"[*] Category slug: '{slug}'")

    session = requests.Session()
    session.headers.update(HEADERS)

    links = get_article_links(slug, limit, session)
    if not links:
        print("[!] No articles found. Check the category name.", file=sys.stderr)
        return []

    results = []
    for i, url in enumerate(links, 1):
        print(f"[{i}/{len(links)}] Scraping: {url}")
        article = parse_article(url, slug, session)
        if article:
            results.append(article)
            print(f"      ✓ '{article['title'][:70]}...'")
        time.sleep(delay)

    print(f"\n[*] Scraped {len(results)} articles.")

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[*] Saved to {output}")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Scrape articles from finance.detik.com by category."
    )
    parser.add_argument(
        "--category", "-c",
        required=True,
        help=(
            "Category slug or friendly name. "
            "E.g.: finansial, berita-ekonomi-bisnis, moneter, "
            "financial, business, economy, crypto, banking ..."
        ),
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=5,
        help="Max number of articles to scrape (default: 5).",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON file path. Prints to stdout if not specified.",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=REQUEST_DELAY,
        help=f"Delay in seconds between requests (default: {REQUEST_DELAY}).",
    )
    args = parser.parse_args()
    scrape(args.category, args.limit, args.output, args.delay)


if __name__ == "__main__":
    main()