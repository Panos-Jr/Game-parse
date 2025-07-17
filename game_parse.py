import sys
import os
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlencode
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

ILLEGAL_CHARACTERS = r'[\\/:*?"<>|{}$!\'"&%`@+=,;.–-]'

def sanitize_title(game_title):
    sanitized = re.sub(ILLEGAL_CHARACTERS, '', game_title)
    sanitized = re.sub(r'[^\x00-\x7F]+', '', sanitized)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return sanitized

def load_sites(json_file='sites.json'):
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_search_url(site, query):
    base = site["url"].rstrip('/')
    query_path = site["path"]
    param = site["query_param"]

    query_formatted = query.replace(' ', '+')

    if param.isnumeric():
        return f"{base}"
    elif param == 'None':
        return f"{base}/{query_path}{query_formatted}"
    elif param:
        return f"{base}/{query_path}?{urlencode({param: query})}"
    else:
        return f"{base}/{query_path}/{query_formatted}/"

def search_site(site, query):
    url = build_search_url(site, query)
    print(url)
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        matches = []
        for a in soup.find_all('a', href=True):
            if sanitize_title(query.lower()) in sanitize_title(a.text.lower()):
                link = a['href']
                if not link.startswith('http'):
                    link = f"{site['url'].rstrip('/')}/{link.lstrip('/')}"
                matches.append(link)
        return (site['name'], matches)
    except Exception as e:
        return (site['name'], [f"Error: {e}"])
