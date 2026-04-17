"""
game_parse.py
─────────────
Fast, parallel game-search scraper.

Key improvements over v1:
  • Single shared httpx.Client with HTTP/2 + connection pooling
    → reuses TCP connections across all sites instead of opening a new
      socket for every request
  • lxml parser instead of html.parser  (~3-5x faster BeautifulSoup)
  • Pre-compiled regex patterns cached at import time
  • GOG catalogue cached in memory after the first fetch
  • Persistent Selenium driver (single Chrome instance, serialised with a lock)
  • Per-site handler dispatch table — easy to extend

Install deps:
    pip install httpx[http2] lxml beautifulsoup4 seleniumbase
"""

from __future__ import annotations

import json
import re
import threading
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup
from seleniumbase import Driver

_CLIENT = httpx.Client(
    http2=True,
    follow_redirects=True,
    timeout=httpx.Timeout(connect=6.0, read=15.0, write=6.0, pool=6.0),
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    },
    limits=httpx.Limits(max_connections=40, max_keepalive_connections=30),
)

_selenium_lock  = threading.Lock()
_selenium_driver: Driver | None = None


def _get_driver() -> Driver:
    global _selenium_driver
    if _selenium_driver is None:
        _selenium_driver = Driver(uc=True)
    return _selenium_driver


def close_selenium_driver() -> None:
    global _selenium_driver
    if _selenium_driver:
        try:
            _selenium_driver.quit()
        except Exception:
            pass
        _selenium_driver = None


_GOG_API   = "https://gog-games.to/api/web/all-games"
_GOG_BASE  = "https://gog-games.to/game/"
_gog_lock  = threading.Lock()
_gog_index: dict[str, str] | None = None


def _ensure_gog_cache() -> dict[str, str]:
    global _gog_index
    with _gog_lock:
        if _gog_index is None:
            resp = _CLIENT.get(_GOG_API)
            resp.raise_for_status()
            _gog_index = {
                g["slug"]: _clean(g.get("title", "")).lower()
                for g in resp.json()
            }
    return _gog_index

_ILLEGAL   = re.compile(r'[\\/:*?"<>|{}$!\'"&%`@+=,;.\-]')
_NON_ASCII = re.compile(r'[^\x00-\x7F]+')
_SPACES    = re.compile(r'\s+')


def _clean(text: str) -> str:
    #Strip punctuation, non-ASCII, and whitespace
    s = _ILLEGAL.sub('', text)
    s = _NON_ASCII.sub('', s)
    return _SPACES.sub('', s)


def load_sites(json_file: str = 'sites.json') -> list[dict]:
    with open(json_file, encoding='utf-8') as f:
        return json.load(f)


def _build_url(site: dict, query: str) -> str:
    base = site["query_url"]
    if 'elamigos' in base:
        return base          # static listing page — no query string
    return f"{base}{quote(query, safe='')}"


def _soup(html: str) -> BeautifulSoup:
    """Parse HTML with lxml when available, falling back to html.parser."""
    try:
        return BeautifulSoup(html, 'lxml')
    except Exception:
        return BeautifulSoup(html, 'html.parser')


def _extract_links(html: str, query: str, site_url: str) -> list[str]:
    """Return hrefs whose link text fuzzy-matches the query."""
    q     = _clean(query).lower()
    base  = site_url.rstrip('/')
    links = []
    for a in _soup(html).find_all('a', href=True):
        if q in _clean(a.get_text()).lower():
            href = a['href']
            if not href.startswith('http'):
                href = f"{base}/{href.lstrip('/')}"
            links.append(href)
    return links

#site-specific exceptions
def _search_gog(site: dict, query: str) -> tuple[str, list[str]]:
    index   = _ensure_gog_cache()
    q_clean = _clean(query).lower()
    links   = [_GOG_BASE + slug for slug, title in index.items() if q_clean in title]
    return (site['name'], links)


def _search_elamigos(site: dict, query: str) -> tuple[str, list[str]]:
    url  = _build_url(site, query)
    resp = _CLIENT.get(url, headers={"User-Agent": "MyBot/1.0 (+bot@example.com)"})
    resp.raise_for_status()

    pattern = re.compile(r"\b" + re.escape(query) + r"\b", re.I)
    results: list[str] = []

    for node in _soup(resp.text).find_all(string=pattern):
        parent     = node.parent
        candidates = (
            [parent]
            + list(parent.find_next_siblings(limit=3))
            + list(parent.find_previous_siblings(limit=3))
        )
        for c in candidates:
            a = c.find('a', href=True) if hasattr(c, 'find') else None
            if a:
                results.append(urljoin(url, a['href']))
                break

    return (site['name'], results)


def _search_generic(site: dict, query: str) -> tuple[str, list[str]]:
    """Try plain HTTP first; fall back to Selenium when blocked."""
    url  = _build_url(site, query)
    html = None

    if not site.get('requires_selenium', False):
        try:
            resp = _CLIENT.get(url)
            if resp.status_code != 403:
                resp.raise_for_status()
                html = resp.text
        except (httpx.HTTPStatusError, httpx.RequestError):
            pass

    if html is None:
        with _selenium_lock:
            drv = _get_driver()
            drv.uc_open_with_reconnect(url, 10)
            drv.uc_gui_click_captcha()
            html = drv.page_source

    return (site['name'], _extract_links(html, query, site['url']))



#new site handlers here; search_site() needs no changes

_DISPATCH: dict[str, callable] = {
    'https://gog-games.to':  _search_gog,
    'https://elamigos.site': _search_elamigos,
}


def search_site(site: dict, query: str) -> tuple[str, list[str]]:
    for prefix, handler in _DISPATCH.items():
        if site.get('url', '').startswith(prefix):
            return handler(site, query)
    return _search_generic(site, query)