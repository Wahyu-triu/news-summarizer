"""
beritasatu_scraper.py
---------------------
Scrapes articles from beritasatu.com by category.

NOTE: BeritaSatu uses bot-detection (Cloudflare). This scraper uses
`cloudscraper` (pip install cloudscraper) to bypass it automatically.
If cloudscraper is unavailable it falls back to `requests` with a rotated
User-Agent, but success is not guaranteed without the bypass library.

Install dependencies:
    pip install requests beautifulsoup4 cloudscraper

Usage:
    python beritasatu_scraper.py --category ekonomi
    python beritasatu_scraper.py --category business --limit 10
    python beritasatu_scraper.py --category finansial --output results.json
    python beritasatu_scraper.py --category perbankan --limit 20 --delay 2

Available categories (English aliases + Indonesian slugs):

    Top-level sections:
        ekonomi             → Ekonomi
        nasional            → Nasional
        megapolitan         → Megapolitan
        internasional       → Internasional
        olahraga            → Olahraga
        teknologi           → Teknologi
        otomotif            → Otomotif
        lifestyle           → Lifestyle
        hiburan             → Hiburan
        kesehatan           → Kesehatan
        properti            → Properti

    Ekonomi sub-categories (ekonomi/<sub>):
        bisnis              → Bisnis
        finansial           → Finansial
        perbankan           → Perbankan
        investasi           → Investasi
        energi              → Energi
        industri            → Industri
        infrastruktur       → Infrastruktur
        agroindustri        → Agroindustri
        ukm                 → UKM

Output fields per article:
    category, title, author, date_publish, content, date_scraped
"""

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from seleniumbase import Driver

# Try to import cloudscraper (best for Cloudflare-protected sites)
try:
    import cloudscraper
    _HAS_CLOUDSCRAPER = True
except ImportError:
    _HAS_CLOUDSCRAPER = False

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://www.beritasatu.com"

# Rotate through several realistic User-Agents
_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
]

BASE_HEADERS = {
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.beritasatu.com/",
}

REQUEST_DELAY = 2.0  # seconds between requests (slightly higher due to bot-detection)

# ── Category normalisation ───────────────────────────────────────────────────

_CATEGORY_ALIAS: dict[str, str] = {
    # Economy / business
    "economy":          "ekonomi",
    "economic":         "ekonomi",
    "business":         "ekonomi/bisnis",
    "financial":        "ekonomi/finansial",
    "finance":          "ekonomi/finansial",
    "banking":          "ekonomi/perbankan",
    "investment":       "ekonomi/investasi",
    "energy":           "ekonomi/energi",
    "industry":         "ekonomi/industri",
    "infrastructure":   "ekonomi/infrastruktur",
    "agro":             "ekonomi/agroindustri",
    "agriculture":      "ekonomi/agroindustri",
    "smb":              "ekonomi/ukm",
    "sme":              "ekonomi/ukm",
    # Other sections
    "national":         "nasional",
    "politics":         "nasional",
    "metro":            "megapolitan",
    "jakarta":          "megapolitan",
    "international":    "internasional",
    "world":            "internasional",
    "sports":           "olahraga",
    "sport":            "olahraga",
    "tech":             "teknologi",
    "technology":       "teknologi",
    "automotive":       "otomotif",
    "cars":             "otomotif",
    "lifestyle":        "lifestyle",
    "entertainment":    "hiburan",
    "health":           "kesehatan",
    "property":         "properti",
}

_EKONOMI_SUBS = {
    "bisnis", "finansial", "perbankan", "investasi",
    "energi", "industri", "infrastruktur", "agroindustri", "ukm",
}


def resolve_category(raw: str) -> str:
    """
    Return the URL path for the given category input.

    Examples
    --------
    "economy"     → "ekonomi"
    "business"    → "ekonomi/bisnis"
    "financial"   → "ekonomi/finansial"
    "perbankan"   → "ekonomi/perbankan"   (bare sub-slug auto-prefixed)
    "teknologi"   → "teknologi"
    """
    slug = raw.strip().lower().replace(" ", "-")

    # 1. English alias
    if slug in _CATEGORY_ALIAS:
        return _CATEGORY_ALIAS[slug]

    # 2. Bare ekonomi sub-slug → prefix
    if slug in _EKONOMI_SUBS:
        return f"ekonomi/{slug}"

    # 3. Already a full path → pass through
    return slug


# ── HTTP session factory ─────────────────────────────────────────────────────

def _make_session(ua_index: int = 0):
    """
    Return a cloudscraper session (preferred) or plain requests.Session.
    cloudscraper automatically handles Cloudflare JS challenges.
    """
    ua = _USER_AGENTS[ua_index % len(_USER_AGENTS)]
    headers = {**BASE_HEADERS, "User-Agent": ua}

    if _HAS_CLOUDSCRAPER:
        session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
    else:
        print(
            "[WARN] cloudscraper not installed. Bot-detection bypass is limited.\n"
            "       Install it with: pip install cloudscraper",
            file=sys.stderr,
        )
        session = requests.Session()

    session.headers.update(headers)
    return session

def _make_selenium_session():
    """
    Return a SeleniumBase Driver session for scraping.

    Note: Selenium is heavier and more complex than cloudscraper, but can be
    used as an alternative if cloudscraper fails. It may require additional
    setup (e.g. installing a compatible WebDriver).
    """
    driver = Driver(browser="chrome", headless=True)
    # driver.set_user_agent(_USER_AGENTS[0])
    return driver

# ── HTTP helpers ─────────────────────────────────────────────────────────────

def get_soup(url: str, session) -> BeautifulSoup | None:
    try:
        # resp = session.get(url)
        session.get(url)

        # Wait randomly for the invisible challenge to complete
        time.sleep(random.uniform(4, 7))
        # resp.raise_for_status()

        # Selenium session
        return BeautifulSoup(session.page_source, "html.parser")
    except Exception as exc:
        print(f"  [WARN] Could not fetch {url}: {exc}", file=sys.stderr)
        return None


# ── Listing page → article links ─────────────────────────────────────────────

def get_article_links(category_path: str, limit: int, session) -> list[str]:
    """
    Scrape article links from a BeritaSatu category page.

    Article URLs follow one of:
        https://www.beritasatu.com/<section>/<numeric-id>/<slug>
        https://www.beritasatu.com/network/<partner>/<id>/<slug>

    We only collect the main beritasatu.com/<section>/<id>/<slug> pattern
    to avoid partner/network articles that may have different structures.
    """
    listing_url = f"{BASE_URL}/{category_path}"
    print(f"[*] Fetching listing: {listing_url}")
    soup = get_soup(listing_url, session)
    if not soup:
        return []

    # Match: /ekonomi/2997585/title-slug  (section/numeric-id/slug)
    article_re = re.compile(
        r"https://www\.beritasatu\.com"
        r"/(?!network/)(?:[^/]+)"          # section (not "network")
        r"/(\d{5,})"                        # numeric article ID (≥5 digits)
        r"/[^\"'\s?#]+"                     # slug
    )

    seen: set[str] = set()
    links: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # Make relative URLs absolute
        if href.startswith("/") and not href.startswith("//"):
            href = BASE_URL + href
        href = href.split("?")[0]  # strip UTM/query params

        if article_re.match(href) and href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= limit:
            break

    print(f"[*] Found {len(links)} article link(s).")
    return links


# ── Article page parser ───────────────────────────────────────────────────────

def parse_article(url: str, session) -> dict | None:
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
            title = og["content"].replace("- BeritaSatu", "").replace("- Beritasatu.com", "").strip()

    # ── author ─────────────────────────────────────────────────────────────
    # BeritaSatu shows the photographer/reporter as a caption inside the article,
    # e.g. "(Beritasatu.com/Joanito de Saojoao)" or via meta name="author".
    author: str = "N/A"

    # 1. <meta name="author" content="Reporter Name">
    for meta_name in ("author", "sailthru.author", "dc.creator"):
        tag = soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            val = tag["content"].strip()
            if val.lower() not in ("beritasatu.com", "berita satu", "b-universe", ""):
                author = val
                break

    if author == "N/A":
        # 2. Byline element in page body
        byline = soup.find(
            True,
            class_=re.compile(r"author|reporter|penulis|byline|journalist", re.I),
        )
        if byline:
            text = byline.get_text(strip=True)
            text = re.sub(r"^(Oleh|By|Penulis|Reporter)\s*[:\-]?\s*", "", text, flags=re.I)
            if text:
                author = text

    if author == "N/A":
        # 3. Inline caption pattern: "(Beritasatu.com/Name)" or "Foto: Name"
        body_text = soup.get_text(separator="\n")
        cap_match = re.search(
            r"\(Beritasatu\.com/([^)]+)\)", body_text, re.I
        )
        if cap_match:
            author = cap_match.group(1).strip()

    if author == "N/A":
        # 4. Schema.org author in JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json as _json
                data = _json.loads(script.string or "{}")
                # Handle both object and list
                if isinstance(data, list):
                    data = data[0] if data else {}
                if "author" in data:
                    a_field = data["author"]
                    if isinstance(a_field, dict):
                        author = a_field.get("name", "N/A")
                    elif isinstance(a_field, list) and a_field:
                        author = a_field[0].get("name", "N/A")
                    elif isinstance(a_field, str):
                        author = a_field
                    if author != "N/A":
                        break
            except Exception:
                continue

    # ── date_publish ────────────────────────────────────────────────────────
    # BeritaSatu uses standard OG / article meta tags
    date_publish: str = "N/A"

    for prop in ("article:published_time", "og:pubdate", "article:modified_time"):
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            raw = tag["content"].strip()
            try:
                date_publish = datetime.fromisoformat(raw).isoformat()
            except ValueError:
                date_publish = raw
            break

    if date_publish == "N/A":
        for meta_name in ("publishdate", "dcterms.created", "dc.date", "date"):
            tag = soup.find("meta", attrs={"name": meta_name})
            if tag and tag.get("content"):
                date_publish = tag["content"].strip()
                break

    if date_publish == "N/A":
        # Fallback: <time datetime="...">
        time_tag = soup.find("time")
        if time_tag:
            date_publish = time_tag.get("datetime") or time_tag.get_text(strip=True)

    if date_publish == "N/A":
        # Fallback: look for JSON-LD datePublished
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json as _json
                data = _json.loads(script.string or "{}")
                if isinstance(data, list):
                    data = data[0] if data else {}
                if "datePublished" in data:
                    raw = data["datePublished"]
                    try:
                        date_publish = datetime.fromisoformat(raw).isoformat()
                    except ValueError:
                        date_publish = raw
                    break
            except Exception:
                continue

    # ── category ────────────────────────────────────────────────────────────
    # Read from breadcrumb nav or og:section
    category: str = "N/A"

    crumbs = soup.select(
        "ol.breadcrumb a, ul.breadcrumb a, "
        "nav.breadcrumb a, div.breadcrumb a, "
        "span.breadcrumb a"
    )
    if crumbs:
        section_crumbs = [
            c.get_text(strip=True) for c in crumbs
            if c.get_text(strip=True).lower() not in ("home", "beranda", "beritasatu", "")
        ]
        if section_crumbs:
            category = section_crumbs[-1]

    if category == "N/A":
        og_section = soup.find("meta", property="article:section")
        if og_section and og_section.get("content"):
            category = og_section["content"].strip()

    if category == "N/A":
        # Derive from URL path: /ekonomi/<id>/slug → "Ekonomi"
        parts = url.replace(BASE_URL + "/", "").split("/")
        category = parts[0].replace("-", " ").title() if parts else "N/A"

    # ── content ─────────────────────────────────────────────────────────────
    content = _extract_content(soup)

    return {
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
    Extract clean body text from a BeritaSatu article page.

    BeritaSatu wraps article body in one of:
        <div class="detail-in">
        <div class="detail-news-content">
        <div class="article-content">
        <div class="post-content">
        <article>
    """
    container_selectors = [
        "div.detail-in",
        "div.detail-news-content",
        "div.detail-content",
        "div[class*='detail-news']",
        "div[class*='article-content']",
        "div[class*='post-content']",
        "div[class*='news-content']",
        "article",
    ]

    body = None
    for sel in container_selectors:
        body = soup.select_one(sel)
        if body:
            break

    if not body:
        return "N/A"

    # Remove noise elements
    for tag in body.find_all(
        ["script", "style", "ins", "iframe", "figure",
         "aside", "blockquote", "noscript", "svg"]
    ):
        tag.decompose()

    # Strip ad divs, social share bars, read-more boxes
    for tag in body.find_all(True):
        try:
            cls = " ".join(tag.get("class", []))
            text_lc = tag.get_text().lower()
            if any(
                kw in cls.lower()
                for kw in (
                    "ads", "iklan", "related", "baca-juga", "read-more",
                    "rekomendasi", "share", "sosmed", "tag-artikel",
                    "widget", "promo", "newsletter", "subscription",
                    "more-articles", "next-article", "sidebar",
                )
            ):
                tag.decompose()
            elif tag.name in ("strong", "b") and re.match(r"baca\s+juga", text_lc, re.I):
                parent = tag.find_parent("p")
                if parent:
                    parent.decompose()
        except Exception:
            continue

    # Collect clean paragraph text
    paragraphs: list[str] = []
    for tag in body.find_all(["p", "h2", "h3", "h4", "li"]):
        text = tag.get_text(separator=" ", strip=True)
        if (
            len(text) > 20
            and "ADVERTISEMENT" not in text.upper()
            and not re.match(r"^Baca\s+juga", text, re.I)
            and not re.match(r"^(Share|Bagikan|Tags?)\s*[:\-]?", text, re.I)
        ):
            paragraphs.append(text)

    return "\n\n".join(paragraphs) if paragraphs else body.get_text(separator="\n", strip=True)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def scrape(category_raw: str, limit: int, output: str | None, delay: float) -> list[dict]:
    category_path = resolve_category(category_raw)
    print(f"[*] Resolved category path : '{category_path}'")

    if not _HAS_CLOUDSCRAPER:
        print(
            "[WARN] cloudscraper not found. Install it for better bot-detection bypass:\n"
            "       pip install cloudscraper",
            file=sys.stderr,
        )

    # session = _make_session(ua_index=0)
    session = _make_selenium_session()

    links = get_article_links(category_path, limit, session)
    if not links:
        print(
            "[!] No articles found. Possible causes:\n"
            "    1. Bot-detection blocked the request → install cloudscraper\n"
            "    2. Category name is wrong → check the category map below\n\n"
            "    Valid examples: ekonomi, bisnis, finansial, perbankan,\n"
            "                    economy, business, financial, banking,\n"
            "                    teknologi, nasional, olahraga ...",
            file=sys.stderr,
        )
        return []

    results: list[dict] = []
    for i, url in enumerate(links, 1):
        print(f"[{i}/{len(links)}] Scraping: {url}")

        # Rotate user-agent per article for better evasion
        session.headers["User-Agent"] = _USER_AGENTS[i % len(_USER_AGENTS)]

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
            "Scrape news articles from beritasatu.com by category.\n\n"
            "Accepts both English aliases and native Indonesian slugs:\n"
            "  English  : economy, business, financial, banking, tech ...\n"
            "  Indonesian: ekonomi, bisnis, finansial, perbankan, teknologi ...\n\n"
            "NOTE: Install cloudscraper for bot-detection bypass:\n"
            "      pip install cloudscraper"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--category", "-c",
        required=True,
        help="News category (English alias or Indonesian slug).",
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