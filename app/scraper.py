"""
Scraper using logic from fridasor/tabscraper (github.com/fridasor/tabscraper)
"""
import re
import shutil
import subprocess
import urllib.parse

import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://www.ultimate-guitar.com/',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-User': '?1',
    'Sec-Fetch-Dest': 'document',
    'Sec-CH-UA': '"Chromium";v="125", "Not A(Brand)";v="8", "Google Chrome";v="125"',
    'Sec-CH-UA-Mobile': '?0',
    'Sec-CH-UA-Platform': '"Linux"',
}


def _looks_like_html(text):
    if not isinstance(text, str):
        return False
    lower_text = text.lower()
    return '<html' in lower_text or '<!doctype html' in lower_text


def _curl_fetch_text(url):
    if shutil.which('curl') is None:
        raise RuntimeError('curl is required for Ultimate Guitar fetches without Brotli support.')

    cmd = [
        'curl', '--compressed', '-L', '-s',
        '-A', DEFAULT_HEADERS['User-Agent'],
        '-H', f"Accept: {DEFAULT_HEADERS['Accept']}",
        '-H', f"Accept-Language: {DEFAULT_HEADERS['Accept-Language']}",
        '-H', f"Referer: {DEFAULT_HEADERS['Referer']}",
        '-H', f"Sec-Fetch-Site: {DEFAULT_HEADERS['Sec-Fetch-Site']}",
        '-H', f"Sec-Fetch-Mode: {DEFAULT_HEADERS['Sec-Fetch-Mode']}",
        '-H', f"Sec-Fetch-User: {DEFAULT_HEADERS['Sec-Fetch-User']}",
        '-H', f"Sec-Fetch-Dest: {DEFAULT_HEADERS['Sec-Fetch-Dest']}",
        '-H', f"Sec-CH-UA: {DEFAULT_HEADERS['Sec-CH-UA']}",
        '-H', f"Sec-CH-UA-Mobile: {DEFAULT_HEADERS['Sec-CH-UA-Mobile']}",
        '-H', f"Sec-CH-UA-Platform: {DEFAULT_HEADERS['Sec-CH-UA-Platform']}",
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"curl failed to fetch {url}: {stderr or 'unknown error'}")
    if not _looks_like_html(result.stdout):
        raise RuntimeError(f'curl returned a non-HTML response for {url}.')
    return result.stdout


def browser_get(url):
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if response.status_code == 200 and _looks_like_html(response.text):
            return response.text
    except requests.RequestException:
        response = None

    if shutil.which('curl'):
        return _curl_fetch_text(url)

    if response is not None:
        raise RuntimeError(
            f'Unable to fetch {url} (status code {response.status_code}). '
            'Install curl or Brotli support to retrieve Ultimate Guitar pages.'
        )

    raise RuntimeError(
        'Unable to fetch Ultimate Guitar pages. Install curl or Brotli support to retrieve Ultimate Guitar pages.'
    )


def search_ultimate_guitar(query):
    """Search UG and return list of tab results."""
    try:
        if not query or not query.strip():
            return [], "Search query is empty."

        url = 'https://www.ultimate-guitar.com/search.php?search_type=title&value=' + urllib.parse.quote_plus(query.strip())
        page_text = browser_get(url)
        s = page_text.replace('&quot;', '"')

        results_start = s.find('"results":')
        if results_start == -1:
            return [], "Could not parse search results."

        array_start = s.find('[', results_start)
        if array_start == -1:
            return [], "Could not parse search results."

        depth = 0
        end_idx = None
        for i, ch in enumerate(s[array_start:], start=array_start):
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        if end_idx is None:
            return [], "Could not parse search results."

        tabs_str = s[array_start:end_idx]
        results = _parse_results(tabs_str)
        if not results:
            return [], "No results found."
        return results, None

    except RuntimeError as e:
        return [], str(e)
    except requests.ConnectionError:
        return [], "No internet connection."
    except requests.Timeout:
        return [], "Request timed out."
    except Exception as e:
        return [], f"Error: {e}"


def _parse_results(tabstring):
    """Parse tab dictionaries from UG search result string."""
    IRRELEVANT = ['Bass Tabs', 'Video', 'Pro', 'Ukulele']

    tab_matches = list(re.finditer(r'"id":', tabstring))
    results = []

    for i, match in enumerate(tab_matches[:-1]):
        start = match.span()[0]
        end = tab_matches[i + 1].span()[0]
        chunk = '{' + tabstring[start:end][:-2]
        chunk = chunk.replace('null', 'None').replace('true', 'True').replace('false', 'False')

        if any(t in chunk for t in IRRELEVANT):
            continue

        try:
            d = eval(chunk)
        except Exception:
            continue

        results.append({
            "id":      d.get("id"),
            "song":    d.get("song_name", "Unknown"),
            "artist":  d.get("artist_name", "Unknown"),
            "type":    d.get("type", "Tab"),
            "rating":  round(d.get("rating") or 0, 2),
            "votes":   d.get("votes", 0) or 0,
            "url":     d.get("tab_url", ""),
            "version": d.get("version", 1),
        })

    return results


def fetch_tab_content(url):
    """Fetch and return cleaned tab text from a UG tab page."""
    try:
        page_text = browser_get(url)
        soup = BeautifulSoup(page_text, "html.parser")

        res = soup.body.find('div', class_='js-store')
        if not res:
            return None, "Could not find tab data on page."
        res = str(res)

        capo_match = re.search(re.escape("capo&quot;:") + r'(\d+),', res)
        T_start = re.search(r'(?<=wiki_tab)[^*]', res)
        T_end   = re.search(r'(?<=revision_id)[^*]', res)

        if not T_start or not T_end:
            return None, "Could not locate tab content in page."

        text = res[T_start.span()[0]:T_end.span()[0]]

        if 'chords' not in url:
            text = text.replace('":{"content":"', '')
            text = text.replace('","revision_id', '')
        else:
            text = text.replace('&quot;:{&quot;content&quot;:&quot;', '')
            text = text.replace('&quot;,&quot;revision_id', '')

        text = text.replace('\\r', '')
        text = text.replace('\\n', '\n')
        for tag in ['[tab]', '[/tab]', '[ch]', '[/ch]']:
            text = text.replace(tag, '')

        if capo_match:
            text = f"Capo at fret {capo_match.group(1)}\n\n" + text

        return text.strip(), None

    except requests.HTTPError as e:
        return None, f"HTTP {e.response.status_code} — could not fetch tab."
    except requests.ConnectionError:
        return None, "No internet connection."
    except requests.Timeout:
        return None, "Request timed out."
    except Exception as e:
        return None, f"Error: {e}"