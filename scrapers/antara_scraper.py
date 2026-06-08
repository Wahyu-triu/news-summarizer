"""
antaranews_scraper.py
---------------------
Scrapes articles from antaranews.com by category.

Usage:
    python antaranews_scraper.py --category ekonomi
    python antaranews_scraper.py --category economy --limit 10
    python antaranews_scraper.py --category bisnis --output results.json
    python antaranews_scraper.py --category financial --limit 20 --delay 2

Available categories (English aliases and Indonesian slugs):

    Top-level:
        ekonomi         → Ekonomi (economy / business)
        politik         → Politik
        hukum           → Hukum
        humaniora       → Humaniora
        tekno           → Teknologi
        olahraga        → Olahraga
        sepakbola       → Sepakbola
        lifestyle       → Lifestyle
        hiburan         → Hiburan / Entertainment
        nusantara       → Nusantara
        dunia           → Dunia / Internasional

    Ekonomi sub-categories (ekonomi/<sub>):
        bisnis          → Bisnis
        finansial       → Finansial
        bursa           → Bursa

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

BASE_URL = "https://www.antaranews.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.antaranews.com/",
}

REQUEST_DELAY = 1.5  # seconds between requests

# ── Category normalisation ───────────────────────────────────────────────────

# English alias → Antara URL path (relative to BASE_URL)
_CATEGORY_ALIAS: dict[str, str] = {
    # Economy / business
    "economy":          "ekonomi",
    "economic":         "ekonomi",
    "economics":        "ekonomi",
    "business":         "ekonomi/bisnis",
    "financial":        "ekonomi/finansial",
    "finance":          "ekonomi/finansial",
    "banking":          "ekonomi/finansial",
    "stock":            "ekonomi/bursa",
    "stocks":           "ekonomi/bursa",
    "exchange":         "ekonomi/bursa",
    # Other top-level
    "politics":         "politik",
    "political":        "politik",
    "law":              "hukum",
    "legal":            "hukum",
    "humanities":       "humaniora",
    "tech":             "tekno",
    "technology":       "tekno",
    "sports":           "olahraga",
    "sport":            "olahraga",
    "football":         "sepakbola",
    "soccer":           "sepakbola",
    "lifestyle":        "lifestyle",
    "entertainment":    "hiburan",
    "regional":         "nusantara",
    "world":            "dunia",
    "international":    "dunia",
}

# Antara ekonomi sub-category slugs
_EKONOMI_SUBS = {"bisnis", "finansial", "bursa"}


def resolve_category(raw: str) -> str:
    """
    Return the URL path for the given category input.

    Examples
    --------
    "economy"   → "ekonomi"
    "business"  → "ekonomi/bisnis"
    "financial" → "ekonomi/finansial"
    "bisnis"    → "ekonomi/bisnis"   (bare Antara sub-slug auto-prefixed)
    "ekonomi"   → "ekonomi"
    "tekno"     → "tekno"
    """
    slug = raw.strip().lower().replace(" ", "-")

    # 1. English alias lookup
    if slug in _CATEGORY_ALIAS:
        return _CATEGORY_ALIAS[slug]

    # 2. Bare ekonomi sub-slug → prefix
    if slug in _EKONOMI_SUBS:
        return f"ekonomi/{slug}"

    # 3. Already a full path like "ekonomi/bisnis" → pass through
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
    Scrape article links from an Antara category listing page.

    Antara article URLs follow the pattern:
        https://www.antaranews.com/berita/<numeric-id>/<slug>

    Video and photo URLs (/video/, /foto/) are excluded to keep only text articles.
    """
    listing_url = f"{BASE_URL}/{category_path}"
    print(f"[*] Fetching listing: {listing_url}")
    soup = get_soup(listing_url, session)
    if not soup:
        return []

    # Match only text article URLs — /berita/<id>/<slug>
    article_re = re.compile(
        r"https://www\.antaranews\.com/berita/\d+/[^\"'\s?#]+"
    )

    seen: set[str] = set()
    links: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip().split("?")[0]  # strip UTM params
        if article_re.match(href) and href not in seen:
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
            title = og["content"].replace(" - ANTARA News", "").strip()

    # ── author ─────────────────────────────────────────────────────────────
    # Antara encodes the reporter as plain text at the bottom of the article:
    #   "Pewarta: Rizka Khaerunnisa"
    # and also via <meta name="author" content="antaranews.com"> (generic).
    # We prefer the Pewarta inline text; fall back to meta if missing.
    author: str = "N/A"

    # Try inline "Pewarta: ..." text first (most specific)
    body_text = soup.get_text(separator="\n")
    pewarta_match = re.search(
        r"Pewarta\s*:\s*([^\n\r]+)", body_text, re.I
    )
    if pewarta_match:
        author = pewarta_match.group(1).strip()

    if author == "N/A":
        # Fallback: structured author meta or byline element
        for meta_name in ("author", "sailthru.author", "dc.creator"):
            tag = soup.find("meta", attrs={"name": meta_name})
            if tag and tag.get("content") and tag["content"].strip() != "antaranews.com":
                author = tag["content"].strip()
                break

    if author == "N/A":
        byline = soup.find(True, class_=re.compile(r"author|byline|reporter", re.I))
        if byline:
            author = byline.get_text(strip=True)

    # ── editor ─────────────────────────────────────────────────────────────
    # Antara often lists "Editor: Name" on the same line block as Pewarta.
    # We capture it as part of author for completeness.
    editor_match = re.search(r"Editor\s*:\s*([^\n\r]+)", body_text, re.I)
    if editor_match:
        editor = editor_match.group(1).strip()
        if author != "N/A":
            author = f"{author} (Editor: {editor})"
        else:
            author = f"Editor: {editor}"

    # ── date_publish ────────────────────────────────────────────────────────
    # Antara uses <meta property="article:published_time"> with ISO 8601 format:
    #   "2026-06-05T23:01:07+07:00"
    date_publish: str = "N/A"

    for prop in ("article:published_time", "og:pubdate"):
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            raw = tag["content"].strip()
            try:
                date_publish = datetime.fromisoformat(raw).isoformat()
            except ValueError:
                date_publish = raw
            break

    if date_publish == "N/A":
        # Fallback: <meta name="publishdate"> or <time datetime="...">
        for meta_name in ("publishdate", "dcterms.created", "dc.date"):
            tag = soup.find("meta", attrs={"name": meta_name})
            if tag and tag.get("content"):
                date_publish = tag["content"].strip()
                break

    if date_publish == "N/A":
        time_tag = soup.find("time")
        if time_tag:
            date_publish = time_tag.get("datetime") or time_tag.get_text(strip=True)

    # ── category ────────────────────────────────────────────────────────────
    # Breadcrumb on Antara: ANTARA > Ekonomi > Finansial > [article title]
    # We take the second-to-last crumb (most specific section, not the article).
    category: str = "N/A"
    crumbs = soup.select("div.breadcrumb a, nav.breadcrumb a, ol.breadcrumb a")
    if crumbs:
        # Skip generic "ANTARA" root crumb; take the last section crumb
        section_crumbs = [c.get_text(strip=True) for c in crumbs if c.get_text(strip=True) != "ANTARA"]
        if section_crumbs:
            category = section_crumbs[-1]

    if category == "N/A":
        # Derive from URL path: /berita/<id>/<slug> → use referring category path
        parts = url.replace(BASE_URL + "/", "").split("/")
        category = parts[0].replace("-", " ").title() if parts else "N/A"

    # ── content ─────────────────────────────────────────────────────────────
    content = _extract_content(soup)

    return {
        "news_platform": "antaranews",
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
    Extract clean article body text from an Antara article page.

    Antara wraps the article body in:
        <div class="post-content">   (primary)
        <div class="detail__body">   (variant)
        <article>                    (fallback)
    """
    container_selectors = [
        "div.post-content",
        "div.detail__body",
        "div[class*='article-content']",
        "div[class*='post-body']",
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
         "aside", "blockquote", "noscript"]
    ):
        tag.decompose()

    # Strip ad divs and "Baca juga" cross-link blocks
    for tag in body.find_all(True):
        try:
            cls = " ".join(tag.get("class", []))
            text_lc = tag.get_text().lower()
            if any(
                kw in cls.lower()
                for kw in ("ads", "iklan", "related", "baca-juga", "rekomendasi",
                            "share", "sosmed", "tag-berita", "copyright")
            ):
                tag.decompose()
            elif tag.name in ("strong", "b") and re.match(r"baca\s+juga", text_lc, re.I):
                # Remove the whole parent <p> that contains only a "Baca juga" link
                parent = tag.find_parent("p")
                if parent:
                    parent.decompose()
        except Exception:
            continue

    # Collect paragraph text — stop before Pewarta/Editor/Copyright footer
    footer_markers = re.compile(
        r"^(Pewarta|Editor|Copyright\s*©|Dilarang\s+keras)", re.I
    )
    paragraphs: list[str] = []
    for tag in body.find_all(["p", "h2", "h3", "h4", "li"]):
        text = tag.get_text(separator=" ", strip=True)
        if footer_markers.match(text):
            break  # stop at Pewarta/Editor footer lines
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
    print(f"[*] Resolved category path : '{category_path}'")

    session = requests.Session()
    session.headers.update(HEADERS)

    links = get_article_links(category_path, limit, session)
    if not links:
        print(
            "[!] No articles found. Check the category name.\n"
            "    Valid examples: ekonomi, bisnis, finansial, bursa,\n"
            "                    economy, business, financial, stock,\n"
            "                    tekno, politik, olahraga, dunia ...",
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
            "Scrape news articles from antaranews.com by category.\n\n"
            "Accepts both English aliases and native Indonesian slugs:\n"
            "  English  : economy, business, financial, stock, tech, politics ...\n"
            "  Indonesian: ekonomi, bisnis, finansial, bursa, tekno, politik ..."
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