"""
Pull public documents from CSISD's own site and BoardBook.

This is a starting point, not a finished crawler — CSISD's site structure
and BoardBook's agenda URLs will need occasional adjustment. It's built to
be polite (rate-limited, identifies itself) and idempotent (skips files
it already has).

Usage:
    python src/scrape.py --out data/raw
"""
import argparse
import hashlib
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "csisd-rag-research-bot/0.1 (personal research project; "
                  "contact: replace-with-your-email@example.com)"
}

# Starting points. Add more listing/index pages here as you find them —
# e.g. specific board-meeting-archive years, policy manual sections, etc.
SEED_PAGES = [
    "https://www.csisd.org/news/what_s_new",
    "https://www.csisd.org/departments/business_services",
]

RATE_LIMIT_SECONDS = 1.5


def fetch(url: str) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        print(f"  [skip] {url} -> {e}")
        return None


def find_pdf_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            links.append(urljoin(base_url, href))
    return links


def save_pdf(url: str, out_dir: Path) -> None:
    # Use a short hash + filename so re-runs don't re-download existing files
    name = Path(urlparse(url).path).name or "file.pdf"
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    dest = out_dir / f"{digest}_{name}"
    if dest.exists():
        return
    resp = fetch(url)
    if resp is None:
        return
    dest.write_bytes(resp.content)
    print(f"  [saved] {dest.name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output directory for raw PDFs")
    parser.add_argument(
        "--seeds", nargs="*", default=SEED_PAGES,
        help="Override the list of pages to crawl for PDF links"
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for page_url in args.seeds:
        print(f"Crawling {page_url}")
        resp = fetch(page_url)
        if resp is None:
            continue
        pdf_links = find_pdf_links(resp.text, page_url)
        print(f"  found {len(pdf_links)} PDF link(s)")
        for link in pdf_links:
            save_pdf(link, out_dir)
            time.sleep(RATE_LIMIT_SECONDS)
        time.sleep(RATE_LIMIT_SECONDS)

    print(
        "\nDone with automated seeds. For BoardBook agenda packets, "
        "TEA PEIMS downloads, and anything behind a search form, "
        "download manually into the same output directory — this "
        "scraper only follows plain <a href='*.pdf'> links on static pages."
    )


if __name__ == "__main__":
    main()
