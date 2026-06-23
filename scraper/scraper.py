#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chengcheng EGG - egg price scraper v3
Playwright headless browser edition

Strategy:
1. Sogou WeChat search -> browser follows JS redirect -> parse mp.weixin.qq.com article
2. Baidu search -> follow links -> parse content
3. Search result snippet parsing (last resort fallback)
4. requests-based fallback (if Playwright not installed)
"""

import json
import re
import os
import sys
import time
import subprocess
import urllib.parse
from datetime import datetime, timezone, timedelta

# Force UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

CST = timezone(timedelta(hours=8))
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'prices.json')

# Try importing Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[WARN] Playwright not available, will use requests fallback")

import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}
TIMEOUT = 20

# ============ Sources ============
SOURCES = {
    "guantao": {
        "name": "\u6cb3\u5317\u9986\u9676\u9e21\u86cb\u62a5\u4ef7",
        "wechat_id": "hbgtjdbj",
        "search_keywords": ["\u9986\u9676\u9e21\u86cb\u62a5\u4ef7", "\u6cb3\u5317\u9986\u9676 \u9e21\u86cb\u4ef7\u683c"],
    },
    "jiameixian": {
        "name": "\u5bb6\u7f8e\u9c9c\u9e21\u86cb",
        "wechat_id": "XSJMXJD",
        "search_keywords": ["\u5bb6\u7f8e\u9c9c\u9e21\u86cb\u62a5\u4ef7", "\u4f73\u7f8e\u9c9c \u9e21\u86cb\u4ef7\u683c"],
    },
    "xishui": {
        "name": "\u6d60\u6c34\u86cb\u54c1\u4ea4\u6613\u4e2d\u5fc3",
        "wechat_id": "",
        "search_keywords": ["\u6d60\u6c34\u9e21\u86cb\u4ef7\u683c", "\u6d60\u6c34 \u7c89\u86cb \u62a5\u4ef7"],
    },
    "sanjian": {
        "name": "\u6e56\u5357\u4e09\u5c16\u519c\u7267\u516c\u53f8",
        "wechat_id": "hnsjnm",
        "search_keywords": ["\u4e09\u5c16\u519c\u7267 \u9e21\u86cb", "\u6e56\u5357\u4e09\u5c16 \u86cb\u4ef7"],
    },
    "xiji": {
        "name": "\u6cb3\u5317\u8f9b\u96c6\u57ce\u65b9\u86cb\u54c1",
        "wechat_id": "gh_8860042e77c8",
        "search_keywords": ["\u8f9b\u96c6 \u86cb\u54c1 \u4ef7\u683c", "\u6cb3\u5317\u8f9b\u96c6 \u9e21\u86cb\u62a5\u4ef7"],
    },
    "jiujiang": {
        "name": "\u6c5f\u897f\u4e5d\u6c5f\u8910\u58f3\u86cb",
        "wechat_id": "gh_6e1164286ce7",
        "search_keywords": ["\u4e5d\u6c5f \u8910\u58f3\u86cb \u4ef7\u683c", "\u6c5f\u897f\u4e5d\u6c5f \u9e21\u86cb\u62a5\u4ef7"],
    },
    "jingugu": {
        "name": "\u6cb3\u5357\u91d1\u5495\u5495\u86cb\u54c1",
        "wechat_id": "W13253661972",
        "search_keywords": ["\u91d1\u5495\u5495 \u86cb\u54c1 \u4ef7\u683c", "\u6cb3\u5357\u91d1\u5495\u5495 \u9e21\u86cb"],
    },
    "lantian": {
        "name": "\u84dd\u5929\u79bd\u86cb\u8054\u76df",
        "wechat_id": "gh_be44b3efceb2",
        "search_keywords": ["\u84dd\u5929\u79bd\u86cb \u5317\u4eac \u9e21\u86cb", "\u84dd\u5929\u79bd\u86cb\u8054\u76df \u9e21\u86cb\u4ef7\u683c"],
    },
    "qingdao": {
        "name": "\u9752\u5c9b\u86cb\u5546\u8054\u76df",
        "wechat_id": "",
        "search_keywords": ["\u9752\u5c9b \u9e21\u86cb \u62a5\u4ef7", "\u5c71\u4e1c\u9752\u5c9b \u86cb\u4ef7"],
    },
    "xinzhou": {
        "name": "\u6b66\u6c49\u5e02\u65b0\u6d32\u533a\u5144\u5f1f\u86cb\u4e1a",
        "wechat_id": "xiongdidanye666",
        "search_keywords": ["\u5144\u5f1f\u86cb\u4e1a \u7eff\u58f3\u86cb", "\u6b66\u6c49\u65b0\u6d32 \u9e21\u86cb\u62a5\u4ef7"],
    },
    "guiyang": {
        "name": "\u8d35\u9633\u9e21\u86cb\u4ef7\u683c",
        "wechat_id": "gh_ea5f7cbced8d",
        "search_keywords": ["\u8d35\u9633\u9e21\u86cb\u4ef7\u683c", "\u8d35\u5dde\u8d35\u9633 \u9e21\u86cb\u62a5\u4ef7"],
    },
    "jingyao": {
        "name": "\u6cb3\u5317\u4eac\u9976\u86cb\u54c1",
        "wechat_id": "hebeijingraodanpin",
        "search_keywords": ["\u4eac\u9976\u86cb\u54c1 \u4ef7\u683c", "\u6cb3\u5317\u9976\u9633 \u9e21\u86cb\u62a5\u4ef7"],
    },
    "jinlong": {
        "name": "\u664b\u9f99\u9972\u6599",
        "wechat_id": "jinlongsiliao",
        "search_keywords": ["\u664b\u9f99\u9972\u6599 \u9e21\u86cb\u4ef7\u683c", "\u5c71\u897f\u664b\u9f99 \u86cb\u4ef7"],
    },
    "doumei": {
        "name": "\u8c46\u7c95\u6bcf\u65e5\u4ef7\u683c",
        "wechat_id": "",
        "search_keywords": ["\u8c46\u7c95\u6bcf\u65e5\u4ef7\u683c", "\u8c46\u7c95 \u4ef7\u683c \u4eca\u65e5"],
    },
    "zhuochuang": {
        "name": "\u5353\u521b\u8d44\u8baf\u8ba2\u9605\u53f7",
        "wechat_id": "sci-99",
        "search_keywords": ["\u5353\u521b\u8d44\u8baf \u9e21\u86cb\u4ef7\u683c", "\u5353\u521b \u9e21\u86cb\u884c\u60c5"],
    },
}


# ============ Utility Functions ============
def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode('ascii'))


def extract_date_from_text(text):
    if not text:
        return None
    m = re.search(r'(\d{4})\u5e74(\d{1,2})\u6708(\d{1,2})\u65e5', text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r'(\d{1,2})\u6708(\d{1,2})\u65e5', text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        y = datetime.now(CST).year
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def extract_trend_from_title(title):
    if not title:
        return None, None
    if '\u8dcc' in title or '\u964d' in title or '\u843d' in title:
        return 'down', -1
    if '\u6da8' in title or '\u5347' in title:
        return 'up', 1
    if '\u7a33' in title or '\u5e73' in title:
        return 'flat', 0
    return None, None


def extract_number(text):
    if not text:
        return None
    m = re.search(r'(\d+\.?\d*)', text)
    if m:
        val = float(m.group(1))
        return int(val) if val == int(val) else val
    return None


def extract_change(text):
    if not text:
        return None
    text = text.replace('\u2212', '-').replace('\u2014', '-')
    m = re.search(r'([-+]\d+)', text)
    if m:
        return int(m.group(1))
    if '\u6301\u5e73' in text or '\u7a33' in text:
        return 0
    m = re.search(r'[\u25bc\u8dcc\u964d\u843d](\d+)', text)
    if m:
        return -int(m.group(1))
    m = re.search(r'[\u25b2\u6da8\u5347](\d+)', text)
    if m:
        return int(m.group(1))
    return None


# ============ Price Parsing ============
def parse_table_element(table):
    rows = []
    for tr in table.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        if len(cells) < 2:
            continue
        cell_texts = [c.get_text(strip=True) for c in cells]
        first = cell_texts[0]
        if any(h in first for h in ['\u89c4\u683c', '\u54c1\u79cd', '\u51c0\u91cd', '\u7c7b\u522b', '\u9879\u76ee', '\u540d\u79f0']):
            continue
        spec = first
        yesterday = extract_number(cell_texts[1]) if len(cell_texts) > 1 else None
        today = extract_number(cell_texts[2]) if len(cell_texts) > 2 else None
        change = extract_change(cell_texts[3]) if len(cell_texts) > 3 else None
        if today is not None or yesterday is not None:
            rows.append({'spec': spec, 'yesterday': yesterday, 'today': today, 'change': change})
    return rows


def parse_price_line(line):
    """Parse a single text line for price data"""
    rows = []
    # Pattern: "45斤188" or "45斤 188" or "45斤188元"
    for m in re.finditer(r'(\d{2,3})\s*\u65a4\s*(\d{2,3})\s*\u5143?', line):
        rows.append({
            'spec': f'{m.group(1)}\u65a4',
            'today': int(m.group(2)),
            'yesterday': None,
            'change': None,
        })
    # Pattern: "45斤 192 188 -4" (spec yesterday today change)
    if not rows:
        m = re.match(r'(\d{2,3})\s*\u65a4\s+(\d{2,3})\s+(\d{2,3})\s*([-+]?\d+)', line)
        if m:
            rows.append({
                'spec': f'{m.group(1)}\u65a4',
                'yesterday': int(m.group(2)),
                'today': int(m.group(3)),
                'change': int(m.group(4)),
            })
    # Pattern: "45-46斤188" (range spec)
    if not rows:
        for m in re.finditer(r'(\d{2,3})\s*[-\u2013\u2014]\s*(\d{2,3})\s*\u65a4\s*(\d{2,3})', line):
            rows.append({
                'spec': f'{m.group(1)}-\u2013{m.group(2)}\u65a4',
                'today': int(m.group(3)),
                'yesterday': None,
                'change': None,
            })
    return rows


def is_group_name(line):
    """Check if a line looks like a price group header"""
    keywords = ['\u86cb\u6258', '\u7cbe\u54c1', '\u8349\u7eff', '\u7c89\u86cb', '\u7ea2\u86cb',
                '\u8910\u58f3', '\u7eff\u58f3', '\u7bb1', '\u4ef6', '\u6536\u8d2d\u4ef7',
                '\u5747\u4ef7', '\u6279\u53d1', '\u5e02\u573a']
    has_keyword = any(kw in line for kw in keywords)
    has_price = bool(re.search(r'\d{2,3}\s*\u65a4\s*\d{2,3}', line))
    return has_keyword and not has_price and len(line) < 40


def parse_prices_from_content(content_el, text):
    """Extract price groups from article content element and text"""
    groups = []

    # Strategy 1: HTML tables
    for table in content_el.find_all('table'):
        rows = parse_table_element(table)
        if rows:
            groups.append({'name': '', 'rows': rows})

    if groups:
        return groups

    # Strategy 2: Line-by-line text parsing
    lines = text.split('\n')
    current_group = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if is_group_name(line):
            if current_group and current_group['rows']:
                groups.append(current_group)
            current_group = {'name': line, 'rows': []}
            continue

        rows = parse_price_line(line)
        if rows:
            if current_group is None:
                current_group = {'name': '', 'rows': []}
            current_group['rows'].extend(rows)

    if current_group and current_group['rows']:
        groups.append(current_group)

    if groups:
        return groups

    # Strategy 3: Find all "XX斤XXX" patterns in full text
    all_rows = []
    for m in re.finditer(r'(\d{2,3})\s*\u65a4\s*(\d{2,3})', text):
        all_rows.append({
            'spec': f'{m.group(1)}\u65a4',
            'today': int(m.group(2)),
            'yesterday': None,
            'change': None,
        })
    if all_rows:
        groups.append({'name': '', 'rows': all_rows})

    return groups


def parse_prices_from_text(text):
    """Parse prices from plain text (e.g., search snippet)"""
    if not text:
        return []
    all_rows = []
    for m in re.finditer(r'(\d{2,3})\s*\u65a4\s*(\d{2,3})', text):
        all_rows.append({
            'spec': f'{m.group(1)}\u65a4',
            'today': int(m.group(2)),
            'yesterday': None,
            'change': None,
        })
    if all_rows:
        return [{'name': '', 'rows': all_rows}]
    return []


def parse_prices_from_html(html):
    """Parse prices from generic HTML page"""
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text('\n', strip=True)
    content_el = soup.find('body') or soup
    return parse_prices_from_content(content_el, text)


def parse_wechat_article(html):
    """Parse a WeChat article page for price data"""
    soup = BeautifulSoup(html, 'html.parser')

    # Title
    title_el = soup.select_one('#activity-name, .rich_media_title, h1.rich_media_title')
    title = title_el.get_text(strip=True) if title_el else ''

    # Date
    date_str = None
    date_el = soup.select_one('#publish_time, .rich_media_meta_text')
    if date_el:
        date_str = extract_date_from_text(date_el.get_text())
    if not date_str:
        date_str = extract_date_from_text(title)
    if not date_str:
        date_str = extract_date_from_text(soup.get_text()[:500])

    # Content
    content_el = soup.select_one('#js_content, .rich_media_content, #page-content')
    if not content_el:
        return None

    text = content_el.get_text('\n', strip=True)

    # Check for deleted/invalid articles
    if '\u5df2\u5220\u9664' in text or '\u4e0d\u5b58\u5728' in text or len(text) < 20:
        return None

    groups = parse_prices_from_content(content_el, text)

    if not groups:
        return None

    trend, trend_val = extract_trend_from_title(title)

    return {
        'title': title,
        'date': date_str,
        'time': None,
        'trend': trend,
        'trendValue': trend_val,
        'groups': groups,
        'source': 'weixin',
        'content_preview': text[:300],
    }


# ============ Playwright Scraper ============
class PlaywrightScraper:
    def __init__(self):
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self):
        try:
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
        except Exception as e:
            safe_print(f"[playwright] browser launch failed: {e}")
            safe_print("[playwright] installing chromium browser binary...")
            try:
                subprocess.check_call(
                    [sys.executable, '-m', 'playwright', 'install', 'chromium'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120
                )
                safe_print("[playwright] chromium installed, trying system deps...")
                try:
                    subprocess.check_call(
                        ['sudo', sys.executable, '-m', 'playwright', 'install-deps', 'chromium'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120
                    )
                except:
                    safe_print("[playwright] system deps skipped (may still work)")
            except Exception as e2:
                safe_print(f"[playwright] browser install failed: {e2}")
                raise
            # Retry launch after install
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )

        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            locale='zh-CN',
            extra_http_headers={
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
        )
        self.page = self.context.new_page()
        safe_print("[playwright] browser started")

    def close(self):
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.pw:
                self.pw.stop()
        except:
            pass

    def _wait_for_page(self, timeout=5):
        """Wait for page to stabilize"""
        try:
            self.page.wait_for_load_state('domcontentloaded', timeout=15000)
            time.sleep(timeout)
        except:
            pass

    def search_sogou_weixin(self, query, max_results=5):
        """Search Sogou WeChat articles"""
        url = f'https://weixin.sogou.com/weixin?type=2&query={urllib.parse.quote(query)}&ie=utf8'
        safe_print(f"  [sogou] searching: {query}")

        try:
            self.page.goto(url, timeout=30000)
            self._wait_for_page(3)

            # Check for CAPTCHA / anti-spider
            page_content = self.page.content()
            if 'antispider' in self.page.url or '\u9a8c\u8bc1' in page_content[:500]:
                safe_print("  [sogou] CAPTCHA detected, skipping")
                return []

            articles = []

            # Try multiple selectors for article items
            items = self.page.query_selector_all(
                '.news-list li, .news-box, .results > div, div[class*="news"], li[class*="result"]'
            )

            for item in items[:max_results * 2]:
                try:
                    # Try multiple selectors for title link
                    a = item.query_selector('h3 a, h4 a, .txt-box h3 a, a[target="_blank"]')
                    if not a:
                        continue

                    title = a.inner_text().strip()
                    href = a.get_attribute('href')
                    if not title or not href:
                        continue

                    if href.startswith('/'):
                        href = 'https://weixin.sogou.com' + href

                    # Get snippet
                    snippet = ''
                    snippet_el = item.query_selector('.txt-info, p, .s-p')
                    if snippet_el:
                        snippet = snippet_el.inner_text().strip()

                    # Get account name
                    account = ''
                    account_el = item.query_selector('.account, .s-p a')
                    if account_el:
                        account = account_el.inner_text().strip()

                    articles.append({
                        'title': title,
                        'url': href,
                        'snippet': snippet,
                        'account': account,
                    })
                except:
                    continue

            safe_print(f"  [sogou] found {len(articles)} results")
            return articles[:max_results]

        except Exception as e:
            safe_print(f"  [sogou] error: {e}")
            return []

    def fetch_article_via_browser(self, url):
        """Navigate to URL in browser, follow all redirects, return final HTML and URL"""
        try:
            self.page.goto(url, timeout=30000)
            self._wait_for_page(4)

            current_url = self.page.url
            html = self.page.content()

            # Check if we landed on mp.weixin.qq.com
            if 'mp.weixin.qq.com' in current_url:
                safe_print(f"  [fetch] reached WeChat article")
                return html, current_url

            # Check if still on Sogou (redirect didn't work)
            if 'weixin.sogou.com' in current_url:
                safe_print(f"  [fetch] stuck on Sogou, trying click approach")
                # Try clicking the link element
                return None, current_url

            # Maybe it's another site with egg price data
            safe_print(f"  [fetch] landed on: {current_url[:60]}")
            return html, current_url

        except Exception as e:
            safe_print(f"  [fetch] error: {e}")
            return None, None

    def search_baidu(self, query, max_results=5):
        """Search Baidu and return results"""
        url = f'https://www.baidu.com/s?wd={urllib.parse.quote(query)}&ie=utf-8'
        safe_print(f"  [baidu] searching: {query}")

        try:
            self.page.goto(url, timeout=30000)
            self._wait_for_page(3)

            results = []
            items = self.page.query_selector_all('.result, .c-container, .result-op')

            for item in items[:max_results * 2]:
                try:
                    a = item.query_selector('h3 a, .t a, a[href]')
                    if not a:
                        continue

                    title = a.inner_text().strip()
                    href = a.get_attribute('href') or ''
                    if not title or not href:
                        continue

                    snippet = ''
                    snippet_el = item.query_selector('.c-abstract, .c-span-last, p, .content-right')
                    if snippet_el:
                        snippet = snippet_el.inner_text().strip()

                    results.append({
                        'title': title,
                        'url': href,
                        'snippet': snippet,
                    })
                except:
                    continue

            safe_print(f"  [baidu] found {len(results)} results")
            return results[:max_results]

        except Exception as e:
            safe_print(f"  [baidu] error: {e}")
            return []

    def scrape_source(self, key, config):
        """Scrape a single source using all strategies"""
        safe_print(f"\n--- {config['name']} ({key}) ---")

        for keyword in config.get('search_keywords', []):
            # Strategy 1: Sogou WeChat search
            articles = self.search_sogou_weixin(keyword)

            for article in articles[:3]:
                title = article.get('title', '')
                safe_print(f"  [sogou] trying: {title[:50]}")

                html, final_url = self.fetch_article_via_browser(article['url'])
                if not html:
                    continue

                # Try parsing as WeChat article
                data = parse_wechat_article(html)
                if data:
                    data['url'] = final_url
                    safe_print(f"  [OK] parsed {len(data['groups'])} groups from WeChat article")
                    return data

                # Try generic HTML parsing
                groups = parse_prices_from_html(html)
                if groups:
                    safe_print(f"  [OK] parsed {len(groups)} groups (generic)")
                    return {
                        'title': title,
                        'date': extract_date_from_text(title),
                        'time': None,
                        'trend': extract_trend_from_title(title)[0],
                        'trendValue': extract_trend_from_title(title)[1],
                        'groups': groups,
                        'source': 'sogou-web',
                        'url': final_url,
                    }

            # Strategy 1b: Parse snippets as fallback
            for article in articles:
                snippet = article.get('snippet', '')
                if snippet:
                    groups = parse_prices_from_text(snippet)
                    if groups:
                        safe_print(f"  [OK] parsed {len(groups)} groups from snippet")
                        return {
                            'title': article.get('title', ''),
                            'date': extract_date_from_text(article.get('title', '')),
                            'time': None,
                            'trend': extract_trend_from_title(article.get('title', ''))[0],
                            'trendValue': extract_trend_from_title(article.get('title', ''))[1],
                            'groups': groups,
                            'source': 'sogou-snippet',
                            'url': '',
                        }

            # Strategy 2: Baidu search
            baidu_results = self.search_baidu(keyword)

            for result in baidu_results[:3]:
                title = result.get('title', '')
                safe_print(f"  [baidu] trying: {title[:50]}")

                html, final_url = self.fetch_article_via_browser(result['url'])
                if not html:
                    continue

                # Try WeChat article parsing
                data = parse_wechat_article(html)
                if data:
                    data['url'] = final_url
                    safe_print(f"  [OK] parsed {len(data['groups'])} groups from WeChat (via Baidu)")
                    return data

                # Try generic parsing
                groups = parse_prices_from_html(html)
                if groups:
                    safe_print(f"  [OK] parsed {len(groups)} groups (Baidu generic)")
                    return {
                        'title': title,
                        'date': extract_date_from_text(title),
                        'time': None,
                        'trend': extract_trend_from_title(title)[0],
                        'trendValue': extract_trend_from_title(title)[1],
                        'groups': groups,
                        'source': 'baidu',
                        'url': final_url,
                    }

            # Strategy 2b: Parse Baidu snippets
            for result in baidu_results:
                snippet = result.get('snippet', '')
                if snippet:
                    groups = parse_prices_from_text(snippet)
                    if groups:
                        safe_print(f"  [OK] parsed {len(groups)} groups from Baidu snippet")
                        return {
                            'title': result.get('title', ''),
                            'date': extract_date_from_text(result.get('title', '')),
                            'time': None,
                            'trend': extract_trend_from_title(result.get('title', ''))[0],
                            'trendValue': extract_trend_from_title(result.get('title', ''))[1],
                            'groups': groups,
                            'source': 'baidu-snippet',
                            'url': '',
                        }

            time.sleep(1)  # Polite delay between keywords

        safe_print(f"  [FAIL] no data scraped")
        return None


# ============ Requests Fallback Scraper ============
class RequestsScraper:
    """Fallback scraper using requests (used if Playwright not available)"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # Visit Sogou first to get cookies
        try:
            self.session.get('https://weixin.sogou.com/', timeout=10)
        except:
            pass

    def _fetch(self, url, timeout=TIMEOUT):
        try:
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp.text, resp.url
        except Exception as e:
            safe_print(f"  [fetch error] {url[:60]}: {e}")
            return None, None

    def search_sogou_weixin(self, query, max_results=5):
        url = f'https://weixin.sogou.com/weixin?type=2&query={urllib.parse.quote(query)}&ie=utf8'
        safe_print(f"  [sogou-req] searching: {query}")
        html, _ = self._fetch(url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        for item in soup.select('.news-list li, .news-box, div[class*="news"]'):
            a = item.select_one('h3 a, .txt-box h3 a')
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get('href', '')
            if href and not href.startswith('http'):
                href = urllib.parse.urljoin('https://weixin.sogou.com', href)
            snippet_el = item.select_one('.txt-info, p')
            snippet = snippet_el.get_text(strip=True) if snippet_el else ''
            articles.append({'title': title, 'url': href, 'snippet': snippet})

        safe_print(f"  [sogou-req] found {len(articles)} results")
        return articles[:max_results]

    def search_baidu(self, query, max_results=5):
        url = f'https://www.baidu.com/s?wd={urllib.parse.quote(query)}&ie=utf-8'
        safe_print(f"  [baidu-req] searching: {query}")
        html, _ = self._fetch(url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        results = []
        for item in soup.select('.result, .c-container'):
            a = item.select_one('h3 a, .t a')
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get('href', '')
            snippet_el = item.select_one('.c-abstract, p')
            snippet = snippet_el.get_text(strip=True) if snippet_el else ''
            results.append({'title': title, 'url': href, 'snippet': snippet})

        safe_print(f"  [baidu-req] found {len(results)} results")
        return results[:max_results]

    def scrape_source(self, key, config):
        safe_print(f"\n--- {config['name']} ({key}) ---")

        for keyword in config.get('search_keywords', []):
            # Sogou
            articles = self.search_sogou_weixin(keyword)
            for article in articles[:3]:
                safe_print(f"  [sogou-req] trying: {article['title'][:50]}")
                html, final_url = self._fetch(article['url'])
                if not html:
                    continue

                data = parse_wechat_article(html)
                if data:
                    data['url'] = final_url
                    return data

                groups = parse_prices_from_html(html)
                if groups:
                    return {
                        'title': article['title'],
                        'date': extract_date_from_text(article['title']),
                        'time': None,
                        'trend': extract_trend_from_title(article['title'])[0],
                        'trendValue': extract_trend_from_title(article['title'])[1],
                        'groups': groups,
                        'source': 'sogou',
                        'url': final_url,
                    }

            # Snippet fallback
            for article in articles:
                groups = parse_prices_from_text(article.get('snippet', ''))
                if groups:
                    safe_print(f"  [OK] parsed from snippet")
                    return {
                        'title': article['title'],
                        'date': extract_date_from_text(article['title']),
                        'time': None,
                        'trend': extract_trend_from_title(article['title'])[0],
                        'trendValue': extract_trend_from_title(article['title'])[1],
                        'groups': groups,
                        'source': 'sogou-snippet',
                        'url': '',
                    }

            # Baidu
            baidu_results = self.search_baidu(keyword)
            for result in baidu_results[:3]:
                safe_print(f"  [baidu-req] trying: {result['title'][:50]}")
                html, final_url = self._fetch(result['url'])
                if not html:
                    continue

                data = parse_wechat_article(html)
                if data:
                    data['url'] = final_url
                    return data

                groups = parse_prices_from_html(html)
                if groups:
                    return {
                        'title': result['title'],
                        'date': extract_date_from_text(result['title']),
                        'time': None,
                        'trend': extract_trend_from_title(result['title'])[0],
                        'trendValue': extract_trend_from_title(result['title'])[1],
                        'groups': groups,
                        'source': 'baidu',
                        'url': final_url,
                    }

            # Baidu snippet fallback
            for result in baidu_results:
                groups = parse_prices_from_text(result.get('snippet', ''))
                if groups:
                    safe_print(f"  [OK] parsed from Baidu snippet")
                    return {
                        'title': result['title'],
                        'date': extract_date_from_text(result['title']),
                        'time': None,
                        'trend': extract_trend_from_title(result['title'])[0],
                        'trendValue': extract_trend_from_title(result['title'])[1],
                        'groups': groups,
                        'source': 'baidu-snippet',
                        'url': '',
                    }

        safe_print(f"  [FAIL] no data scraped")
        return None


# ============ Data Management ============
def load_existing_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"lastScrapeTime": "", "lastScrapeStatus": "", "sources": {}}


def merge_data(existing, key, config, article_data):
    source_data = existing["sources"].get(key, {})

    # Preserve metadata
    source_data['name'] = config['name']
    if config.get('wechat_id'):
        source_data['wechatId'] = config['wechat_id']

    # Update status and article info
    source_data['status'] = 'updated'
    source_data['article'] = {
        'title': article_data.get('title', ''),
        'date': article_data.get('date', ''),
        'time': article_data.get('time'),
        'url': article_data.get('url', ''),
        'source': article_data.get('source', '')
    }
    source_data['trend'] = article_data.get('trend')
    source_data['trendValue'] = article_data.get('trendValue')

    # Update price groups
    if article_data.get('groups'):
        source_data['groups'] = article_data['groups']

    existing["sources"][key] = source_data
    return existing


# ============ Main ============
def main():
    safe_print("=" * 60)
    safe_print("chengcheng EGG - egg price scraper v3")
    safe_print(f"time: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
    safe_print(f"playwright: {'available' if PLAYWRIGHT_AVAILABLE else 'NOT available, using requests fallback'}")
    safe_print("=" * 60)

    data = load_existing_data()
    safe_print(f"loaded {len(data.get('sources', {}))} existing sources")

    # Choose scraper
    if PLAYWRIGHT_AVAILABLE:
        scraper = PlaywrightScraper()
        scraper.start()
    else:
        scraper = RequestsScraper()

    success_count = 0
    fail_count = 0

    try:
        for key, config in SOURCES.items():
            try:
                article_data = scraper.scrape_source(key, config)
                if article_data:
                    data = merge_data(data, key, config, article_data)
                    success_count += 1
                else:
                    fail_count += 1
                    if key in data["sources"]:
                        data["sources"][key]['status'] = 'pending'
            except Exception as e:
                safe_print(f"  [ERROR] {key}: {e}")
                fail_count += 1

            time.sleep(1)  # Polite delay between sources

    finally:
        if isinstance(scraper, PlaywrightScraper):
            scraper.close()

    # Update metadata
    data["lastScrapeTime"] = datetime.now(CST).isoformat()
    data["lastScrapeStatus"] = f"success:{success_count}, failed:{fail_count}"

    # Save
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    safe_print("\n" + "=" * 60)
    safe_print(f"done: success={success_count}, failed={fail_count}")
    safe_print(f"saved to: {DATA_FILE}")
    safe_print(f"time: {data['lastScrapeTime']}")
    safe_print("=" * 60)


if __name__ == "__main__":
    main()
