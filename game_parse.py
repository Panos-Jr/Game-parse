import json
import re
import requests
from bs4 import BeautifulSoup
from seleniumbase import Driver
from selenium.webdriver.common.by import By
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

ILLEGAL_CHARACTERS = r'[\\/:*?"<>|{}$!\'"&%`@+=,;.-]'

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
        print(f'found it {base}')
        return base
    else:
        return f"{base}{query_formatted}"

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
    url = build_search_url(site, query)
    html = get_page_with_requests(url)

    if 'elamigos' in url:
        print(html)

    if html is None:
        html = get_page_with_selenium(url)

    soup = BeautifulSoup(html, 'html.parser')
    matches = []

    for a in soup.find_all('a', href=True):
        if sanitize_title(query.lower()) in sanitize_title(a.text.lower()):
            link = a['href']
            if not link.startswith('http'):
                link = f"{site['url'].rstrip('/')}/{link.lstrip('/')}"
            matches.append(link)

    return (site['name'], matches)