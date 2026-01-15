import json
import re
import requests
from bs4 import BeautifulSoup
from seleniumbase import Driver
from urllib.parse import urljoin

HEADERS = {"User-Agent": "Mozilla/5.0"}
ILLEGAL_CHARACTERS = r'[\\/:*?"<>|{}$!\'"&%`@+=,;.-]'
API_BASE = "https://gog-games.to/api/web"

def sanitize_title(game_title):
    sanitized = re.sub(ILLEGAL_CHARACTERS, '', game_title)
    sanitized = re.sub(r'[^\x00-\x7F]+', '', sanitized)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    sanitized = ''.join(sanitized.split())
    return sanitized

def load_sites(json_file='sites.json'):
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_search_url(site, query):
    base = site["query_url"]
    query_formatted = query.replace(' ', '%20')
    if 'elamigos' in base:
        return base
    else:
        return f"{base}{query_formatted}"
    
def search_gog_games(query):
    results = []
    try:
        response = requests.get(f"{API_BASE}/all-games", headers=HEADERS, timeout=20)
        response.raise_for_status()
        all_games = response.json()
        query_clean = sanitize_title(query)
        base_url = 'https://gog-games.to/game/'
        for game in all_games:
            title = game.get("title", "")
            if query_clean.lower() in sanitize_title(title).lower():
                results.append(base_url + game.get("slug"))
    except Exception as e:
        print(f"[GOG Games] Error: {e}")
    return results


def get_elamigos_page(url, query):
    results = []
    try:
        resp = requests.get(url, headers={"User-Agent": "MyBot/1.0 (+you@example.com)"})
        resp.raise_for_status()
        html = resp.text

        with open("page.html", "w", encoding="utf-8") as f:
            f.write(html)

        soup = BeautifulSoup(html, "html.parser")
        candidates = soup.find_all(string=re.compile(r"\b" + re.escape(query) + r"\b", flags=re.I))
        for node in candidates:
            parent = node.parent
            a = parent.find("a", href=True)
            if a:
                results.append(urljoin(url, a["href"]))
                continue
            # try siblings
            for sib in parent.find_next_siblings(limit=3):
                a = sib.find("a", href=True)
                if a:
                    results.append(urljoin(url, a["href"]))
                    break
            for sib in parent.find_previous_siblings(limit=3):
                a = sib.find("a", href=True)
                if a:
                    results.append(urljoin(url, a["href"]))
                    break
    except Exception as e:
        print(f"[ElAmigos] Error: {e}")
    return results


def get_page_with_requests(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    if response.status_code == 403:
        return None
    response.raise_for_status()
    return response.text

def get_page_with_selenium(url):
    driver = Driver(uc=True)
    driver.uc_open_with_reconnect(url, 10)
    driver.uc_gui_click_captcha()
    html = driver.page_source
    driver.quit()
    return html

def search_site(site, query):
    """Main entry point for site search."""
    url = build_search_url(site, query)

    if 'https://gog-games.to' in url:
        print('→ Using GOG Games API')
        return (site['name'], search_gog_games(query))

    if 'https://elamigos.site' in url:
        print('→ Parsing ElAmigos')
        return (site['name'], get_elamigos_page(url, query))

    html = get_page_with_requests(url)
    if html is None:
        html = get_page_with_selenium(url)

    soup = BeautifulSoup(html, 'html.parser')
    results = []

    for a in soup.find_all('a', href=True):
        if sanitize_title(query.lower()) in sanitize_title(a.text.lower()):
            link = a['href']
            if not link.startswith('http'):
                link = f"{site['url'].rstrip('/')}/{link.lstrip('/')}"
            results.append(link)

    return (site['name'], results)
