"""
tribunnews_scraper.py
---------------------
Scrapes articles from tribunnews.com by news type / category.

Usage:
    python tribunnews_scraper.py --category bisnis
    python tribunnews_scraper.py --category business --limit 10
    python tribunnews_scraper.py --category finansial --output results.json
    python tribunnews_scraper.py --category teknologi --limit 20 --delay 2

Available category slugs (and English aliases):
    Top-level:
        bisnis          → Bisnis (business / economy)
        teknologi       → Teknologi
        otomotif        → Otomotif
        sport           → Sport
        lifestyle       → Lifestyle / Gaya Hidup
        travel          → Travel
        health          → Kesehatan
        nasional        → Nasional / Politik
        internasional   → Internasional
        entertainment   → Seleb / Entertainment

    Bisnis sub-categories (appended as bisnis/<sub>):
        makro           → Makro
        energi          → Energi
        finansial       → Finansial
        mikro           → Mikro
        investasi       → Investasi
        transportasi    → Transportasi
        infrastruktur   → Infrastruktur
        insight         → Insight
        properti        → Properti

Output fields per article:
    category, title, author, date_publish, content, date_scraped
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://www.tribunnews.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.tribunnews.com/",
}

REQUEST_DELAY = 1.5  # polite crawl delay (seconds)

# ── Category normalisation ───────────────────────────────────────────────────

# English alias → Tribun URL path (relative to BASE_URL)
_CATEGORY_ALIAS: dict[str, str] = {
    # English → top-level slug
    "business":         "bisnis",
    "economy":          "bisnis",
    "finance":          "bisnis/finansial",
    "financial":        "bisnis/finansial",
    "banking":          "bisnis/finansial",
    "macro":            "bisnis/makro",
    "micro":            "bisnis/mikro",
    "energy":           "bisnis/energi",
    "investment":       "bisnis/investasi",
    "transport":        "bisnis/transportasi",
    "transportation":   "bisnis/transportasi",
    "infrastructure":   "bisnis/infrastruktur",
    "property":         "bisnis/properti",
    "tech":             "teknologi",
    "technology":       "teknologi",
    "automotive":       "otomotif",
    "sports":           "sport",
    "lifestyle":        "lifestyle",
    "travel":           "travel",
    "health":           "kesehatan",
    "national":         "nasional",
    "politics":         "nasional",
    "international":    "internasional",
    "entertainment":    "hiburan",
    # common Indonesian aliases that need no remapping still go through
}

# Tribun bisnis sub-category slugs that live under /bisnis/<sub>
_BISNIS_SUBS = {
    "makro", "energi", "finansial", "mikro",
    "investasi", "transportasi", "infrastruktur", "insight", "properti",
}


def resolve_category(raw: str) -> str:
    """
    Return the URL path segment(s) for the given input.

    Examples
    --------
    "business"    → "bisnis"
    "financial"   → "bisnis/finansial"
    "finansial"   → "bisnis/finansial"   (bare Tribun sub-slug)
    "bisnis"      → "bisnis"
    "teknologi"   → "teknologi"
    """
    slug = raw.strip().lower().replace(" ", "-")

    # 1. Direct English alias lookup
    if slug in _CATEGORY_ALIAS:
        return _CATEGORY_ALIAS[slug]

    # 2. Bare Tribun bisnis sub-slug → prefix with "bisnis/"
    if slug in _BISNIS_SUBS:
        return f"bisnis/{slug}"

    # 3. Already a valid path like "bisnis/makro" → pass through
    return slug


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def get_soup(url: str, session: requests.Session) -> BeautifulSoup | None:
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as exc:
        print(f"  [WARN] Could not fetch {url}: {exc}", file=sys.stderr)
        return None


# ── Listing page → article links ─────────────────────────────────────────────

def get_article_links(category_path: str, limit: int, session: requests.Session) -> list[str]:
    """
    Scrape article links from a Tribunnews category listing page.

    Article URLs follow the pattern:
        https://www.tribunnews.com/<section>/<numeric-id>/<slug>
    OR (older posts):
        https://www.tribunnews.com/<section>/YYYY/MM/DD/<slug>
    """
    listing_url = f"{BASE_URL}/{category_path}"
    print(f"[*] Fetching listing: {listing_url}")
    soup = get_soup(listing_url, session)
    if not soup:
        return []

    # Pattern matches both numeric-id and date-based article URLs
    article_re = re.compile(
        r"https://www\.tribunnews\.com/[^/]+"
        r"/(?:\d{4}/\d{2}/\d{2}/|\d+/)"   # date path or numeric id
        r"[^\"'\s?#]+"                      # slug
    )

    seen: set[str] = set()
    links: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # Strip UTM/tracking params
        href = href.split("?")[0]
        if article_re.match(href) and href not in seen:
            # Exclude pagination, index pages, and tag pages
            if "/index-news/" not in href and "/tag/" not in href:
                seen.add(href)
                links.append(href)
        if len(links) >= limit:
            break

    print(f"[*] Found {len(links)} article link(s).")
    return links


# ── Article page parser ───────────────────────────────────────────────────────

def parse_article(url: str, session: requests.Session) -> dict | None:
    soup = get_soup(url, session)
    if not soup:
        return None

    # ── title ──────────────────────────────────────────────────────────────
    title: str = "N/A"
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    else:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = og["content"].replace(" - Tribunnews.com", "").strip()

    # ── author ─────────────────────────────────────────────────────────────
    # Tribun articles show the reporter in a <div class="side-article txt-artikel">
    # or via a meta tag  <meta name="author" content="...">
    author: str = "N/A"

    # Meta tag first
    for meta_name in ("author", "sailthru.author"):
        tag = soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            author = tag["content"].strip()
            break

    if author == "N/A":
        # Byline in body: look for patterns like "Penulis: X" or reporter span
        byline_tag = soup.find(
            True,
            class_=re.compile(r"reporter|penulis|author|byline", re.I),
        )
        if byline_tag:
            author = byline_tag.get_text(separator=" ", strip=True)
            # Strip leading label
            author = re.sub(r"^(Penulis|Reporter|Editor|Oleh)\s*:\s*", "", author, flags=re.I)

    if author == "N/A":
        # Fallback: look for "Editor:" line in the article head area
        editor_tag = soup.find("a", href=re.compile(r"/editor/"))
        if editor_tag:
            author = editor_tag.get_text(strip=True)

    # ── date_publish ────────────────────────────────────────────────────────
    # Tribun renders publish time as:
    #   "Tayang: Sabtu, 6 Juni 2026 16:25 WIB"
    # and also in a <meta> or <time> element.
    date_publish: str = "N/A"

    # 1. <meta name="publishdate"> or article:published_time
    for attr, name in (("name", "publishdate"), ("property", "article:published_time")):
        tag = soup.find("meta", attrs={attr: name})
        if tag and tag.get("content"):
            raw = tag["content"].strip()
            # ISO format directly
            try:
                date_publish = datetime.fromisoformat(raw).isoformat()
            except ValueError:
                # Try "YYYY/MM/DD HH:MM:SS"
                try:
                    date_publish = datetime.strptime(raw, "%Y/%m/%d %H:%M:%S").isoformat()
                except ValueError:
                    date_publish = raw
            break

    if date_publish == "N/A":
        # 2. <time datetime="...">
        time_tag = soup.find("time")
        if time_tag:
            date_publish = time_tag.get("datetime") or time_tag.get_text(strip=True)

    if date_publish == "N/A":
        # 3. Inline text pattern "Tayang: Sabtu, 6 Juni 2026 16:25 WIB"
        tayang_re = re.compile(
            r"Tayang\s*[:\-]?\s*\w+,\s*(\d{1,2}\s+\w+\s+\d{4}\s+\d{2}:\d{2})\s*WIB",
            re.I,
        )
        page_text = soup.get_text(separator=" ")
        m = tayang_re.search(page_text)
        if m:
            date_publish = m.group(1).strip()

    # ── category ────────────────────────────────────────────────────────────
    # Read from breadcrumb; last crumb is the most specific section.
    category: str = "N/A"
    crumbs = soup.select("div#breadcrumb a, nav.breadcrumb a, ol.breadcrumb a, ul.breadcrumb a")
    if crumbs:
        category = crumbs[-1].get_text(strip=True)
    else:
        # Fallback: derive from URL
        parts = url.replace(BASE_URL + "/", "").split("/")
        category = parts[0].replace("-", " ").title() if parts else "N/A"

    # ── content ─────────────────────────────────────────────────────────────
    content = _extract_content(soup)

    return {
        "news_platform": "tribunnews",
        "category":     category,
        "title":        title,
        "author":       author,
        "date_publish": date_publish,
        "content":      content,
        "date_scraped": datetime.now(timezone.utc).isoformat(),
        "source_url":   url,
    }


def _extract_content(soup: BeautifulSoup) -> str:
    """
    Extract clean body text from a Tribun article page.

    Tribun wraps article body in:
        <div class="side-article txt-artikel">  (main article content)
    Older pages may use:
        <div class="txt-article">
        <article> or <div id="article-body">
    """
    container_selectors = [
        "div.side-article.txt-artikel",
        "div.txt-artikel",
        "div.txt-article",
        "div#article-body",
        "div[class*='article-body']",
        "article",
    ]

    body = None
    for sel in container_selectors:
        body = soup.select_one(sel)
        if body:
            break

    if not body:
        return "N/A"

    # Remove noise
    for tag in body.find_all(
        ["script", "style", "ins", "iframe", "figure", "aside", "blockquote"]
    ):
        tag.decompose()

    for tag in body.find_all(True):
        try:
            cls = " ".join(tag.get("class", []))
            text_lc = tag.get_text().lower()
            if any(
                kw in cls.lower()
                for kw in ("ads", "iklan", "related", "baca-juga", "bizzinsight",
                            "rekomendasi", "populer", "terkait", "share", "sosmed")
            ):
                tag.decompose()
            elif tag.name == "strong" and "baca juga" in text_lc:
                tag.decompose()
        except Exception:
            continue

    paragraphs: list[str] = []
    for tag in body.find_all(["p", "h2", "h3", "h4", "li"]):
        text = tag.get_text(separator=" ", strip=True)
        # Skip very short strings, ad banners, and "Baca juga" cross-links
        if (
            len(text) > 20
            and "ADVERTISEMENT" not in text.upper()
            and not re.match(r"^Baca\s+juga", text, re.I)
        ):
            paragraphs.append(text)

    return "\n\n".join(paragraphs) if paragraphs else body.get_text(separator="\n", strip=True)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def scrape(category_raw: str, limit: int, output: str | None, delay: float) -> list[dict]:
    category_path = resolve_category(category_raw)
    print(f"[*] Resolved category path: '{category_path}'")

    session = requests.Session()
    session.headers.update(HEADERS)

    links = get_article_links(category_path, limit, session)
    if not links:
        print(
            "[!] No articles found. Check the category name.\n"
            "    Valid examples: bisnis, business, finansial, financial,\n"
            "                    teknologi, nasional, otomotif, travel ...",
            file=sys.stderr,
        )
        return []

    results: list[dict] = []
    for i, url in enumerate(links, 1):
        print(f"[{i}/{len(links)}] Scraping: {url}")
        article = parse_article(url, session)
        if article:
            results.append(article)
            print(f"      ✓ '{article['title'][:72]}...'")
        time.sleep(delay)

    print(f"\n[*] Scraped {len(results)} article(s) successfully.")

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[*] Results saved to '{output}'")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape news articles from tribunnews.com by category.\n\n"
            "Category accepts both English aliases and native Indonesian slugs:\n"
            "  English  : business, financial, energy, technology, health ...\n"
            "  Indonesian: bisnis, finansial, energi, teknologi, kesehatan ..."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--category", "-c",
        required=True,
        help="News category (English or Indonesian slug).",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=5,
        help="Maximum number of articles to scrape (default: 5).",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Save results to this JSON file. Prints to stdout if omitted.",
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