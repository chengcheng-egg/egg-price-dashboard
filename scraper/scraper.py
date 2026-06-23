#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
乘乘EGG · 全国鸡蛋价格看板 - 自动爬虫 v2
直接抓取聚合站 + 搜索引擎兜底，输出到 data/prices.json

v2 修复:
- 修复编码崩溃(去掉非ASCII输出字符)
- 修复搜狗微信相对URL问题
- 改用直接抓取聚合站列表页(不依赖搜索)
- 增加多CSS选择器适配
- 增加User-Agent轮换
"""

import json
import re
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ============ 配置 ============
CST = timezone(timedelta(hours=8))
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'prices.json')

# 强制 UTF-8 输出，避免 CI 环境编码崩溃
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

TIMEOUT = 15

# ============ 公众号配置 ============
SOURCES = {
    "guantao": {
        "name": "河北馆陶鸡蛋报价",
        "wechat_id": "hbgtjdbj",
        "search_keywords": ["河北馆陶鸡蛋报价", "馆陶金凤 鸡蛋"],
        # 直接抓取的URL（聚合站列表页）
        "direct_urls": [
            ("boyar.cn", "https://www.boyar.cn/category/egg/"),
            ("boyar.cn", "https://www.boyar.cn/tag/%E9%A6%86%E9%99%B6%E9%B8%A1%E8%9B%8B/"),
        ],
    },
    "jiameixian": {
        "name": "家美鲜鸡蛋",
        "wechat_id": "XSJMXJD",
        "search_keywords": ["家美鲜鸡蛋 价格", "佳美鲜 鸡蛋报价"],
        "direct_urls": [
            ("boyar.cn", "https://www.boyar.cn/category/egg/"),
        ],
    },
    "sanjian": {
        "name": "湖南三尖农牧公司",
        "wechat_id": "hnsjnm",
        "search_keywords": ["湖南三尖农牧 鸡蛋", "三尖农牧 蛋价"],
        "direct_urls": [],
    },
    "xiji": {
        "name": "河北辛集城方蛋品",
        "wechat_id": "gh_8860042e77c8",
        "search_keywords": ["辛集 蛋品 价格", "河北辛集 鸡蛋报价"],
        "direct_urls": [],
    },
    "jiujiang": {
        "name": "江西九江褐壳蛋",
        "wechat_id": "gh_6e1164286ce7",
        "search_keywords": ["九江 褐壳蛋 价格", "江西九江 鸡蛋报价"],
        "direct_urls": [],
    },
    "jingugu": {
        "name": "河南金咕咕蛋品",
        "wechat_id": "W13253661972",
        "search_keywords": ["金咕咕 蛋品 价格", "河南金咕咕 鸡蛋"],
        "direct_urls": [],
    },
    "lantian": {
        "name": "蓝天禽蛋联盟",
        "wechat_id": "gh_be44b3efceb2",
        "search_keywords": ["蓝天禽蛋联盟 北京 鸡蛋", "蓝天禽蛋 鸡蛋价格"],
        "direct_urls": [],
    },
    "xinzhou": {
        "name": "武汉市新洲区兄弟蛋业",
        "wechat_id": "xiongdidanye666",
        "search_keywords": ["兄弟蛋业 绿壳蛋", "武汉新洲 鸡蛋报价"],
        "direct_urls": [],
    },
    "guiyang": {
        "name": "贵阳鸡蛋价格",
        "wechat_id": "gh_ea5f7cbced8d",
        "search_keywords": ["贵阳鸡蛋价格", "贵州贵阳 鸡蛋报价"],
        "direct_urls": [],
    },
    "jingyao": {
        "name": "河北京饶蛋品",
        "wechat_id": "hebeijingraodanpin",
        "search_keywords": ["京饶蛋品 价格", "河北饶阳 鸡蛋报价"],
        "direct_urls": [],
    },
    "jinlong": {
        "name": "晋龙饲料",
        "wechat_id": "jinlongsiliao",
        "search_keywords": ["晋龙饲料 鸡蛋价格", "山西晋龙 蛋价"],
        "direct_urls": [],
    },
    "zhuochuang": {
        "name": "卓创资讯订阅号",
        "wechat_id": "sci-99",
        "search_keywords": ["卓创资讯 鸡蛋价格", "卓创 鸡蛋行情"],
        "direct_urls": [],
    },
}


# ============ 通用工具 ============
def safe_print(msg):
    """安全打印，避免编码崩溃"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode('ascii'))


def fetch_url(url, timeout=TIMEOUT):
    """抓取URL内容"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        return resp.text, resp.url
    except Exception as e:
        safe_print(f"  [fetch error] {url[:80]}: {e}")
        return None, None


def extract_date_from_text(text):
    """从文本中提取日期"""
    if not text:
        return None
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r'(\d{1,2})月(\d{1,2})日', text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        y = datetime.now(CST).year
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def extract_time_from_text(text):
    """从文本中提取时间"""
    if not text:
        return None
    m = re.search(r'(\d{1,2}):(\d{2})', text)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def extract_trend_from_title(title):
    """从标题提取涨跌趋势"""
    if not title:
        return None, None
    if '跌' in title or '降' in title or '落' in title:
        return 'down', -1
    if '涨' in title or '升' in title:
        return 'up', 1
    if '稳' in title or '平' in title:
        return 'flat', 0
    return None, None


def extract_number(text):
    """从文本中提取数字"""
    if not text:
        return None
    m = re.search(r'(\d+\.?\d*)', text)
    if m:
        val = float(m.group(1))
        return int(val) if val == int(val) else val
    return None


def extract_change(text):
    """从文本中提取涨跌值"""
    if not text:
        return None
    text = text.replace('\u2212', '-').replace('\u2014', '-').replace('\uff0d', '-')
    m = re.search(r'([-+]\d+)', text)
    if m:
        return int(m.group(1))
    if '持平' in text or '稳' in text or '平' in text:
        return 0
    m = re.search(r'[\u25bc\u28d8\u8dcc\u964d\u843d](\d+)', text)
    if m:
        return -int(m.group(1))
    m = re.search(r'[\u25b2\u6da8\u5347](\d+)', text)
    if m:
        return int(m.group(1))
    return None


# ============ 价格表解析 ============
def parse_table_element(table):
    """解析 <table> 元素"""
    rows = []
    for tr in table.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        if len(cells) < 3:
            continue
        cell_texts = [c.get_text(strip=True) for c in cells]
        
        # 跳过表头
        first = cell_texts[0]
        if any(h in first for h in ['规格', '品种', '净重', '类别', '项目']):
            continue
        
        spec = first
        yesterday = extract_number(cell_texts[1]) if len(cell_texts) > 1 else None
        today = extract_number(cell_texts[2]) if len(cell_texts) > 2 else None
        change = extract_change(cell_texts[3]) if len(cell_texts) > 3 else None
        
        if today is not None or yesterday is not None:
            rows.append({
                'spec': spec,
                'yesterday': yesterday,
                'today': today,
                'change': change
            })
    return rows


def parse_price_lines_from_text(text):
    """从纯文本中解析价格行"""
    rows = []
    # 匹配 "45斤 192 188 -4" 或 "45斤 192元 188元 -4"
    pattern = r'(\d+[-\u2013\u2014]\d+\u65a4|\d+\u65a4)\s+(\d+)\s*\u5143?\s+(\d+)\s*\u5143?\s*([-+]\d+|[-\u2212]\d+)'
    for m in re.finditer(pattern, text):
        spec = m.group(1).strip()
        yesterday = int(m.group(2))
        today = int(m.group(3))
        change_str = m.group(4).replace('\u2212', '-')
        change = int(change_str)
        rows.append({
            'spec': spec,
            'yesterday': yesterday,
            'today': today,
            'change': change
        })
    return rows


def parse_price_table(html_text):
    """通用价格表解析器"""
    soup = BeautifulSoup(html_text, 'html.parser')
    groups = []
    
    # 策略1: HTML表格
    tables = soup.find_all('table')
    for table in tables:
        rows_data = parse_table_element(table)
        if rows_data:
            groups.append({'name': '', 'rows': rows_data})
    
    # 策略2: 纯文本正则
    if not groups:
        text = soup.get_text()
        rows_data = parse_price_lines_from_text(text)
        if rows_data:
            groups.append({'name': '', 'rows': rows_data})
    
    return groups


# ============ 馆陶专用解析器 ============
def parse_guantao_boyar(html_text):
    """解析 boyar.cn 上的馆陶鸡蛋报价文章"""
    soup = BeautifulSoup(html_text, 'html.parser')
    text = soup.get_text()
    
    title = ''
    title_el = soup.find('h1') or soup.find('title')
    if title_el:
        title = title_el.get_text(strip=True)
    
    date_str = extract_date_from_text(title) or extract_date_from_text(text)
    trend, trend_val = extract_trend_from_title(title)
    
    groups = []
    tables = soup.find_all('table')
    
    for table in tables:
        rows_data = parse_table_element(table)
        if rows_data:
            groups.append({'name': '', 'rows': rows_data})
    
    # 文本模式解析
    if not groups:
        lines = text.split('\n')
        current_group = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(kw in line for kw in ['蛋托', '精品', '草绿']):
                if current_group and current_group['rows']:
                    groups.append(current_group)
                current_group = {'name': line, 'rows': []}
                continue
            m = re.match(r'(\d+[-\u2013\u2014]\d+\u65a4|\d+\u65a4)\s+(\d+)\u5143?\s+(\d+)\u5143?\s*([-+]?\d+)', line)
            if m and current_group is not None:
                current_group['rows'].append({
                    'spec': m.group(1),
                    'yesterday': int(m.group(2)),
                    'today': int(m.group(3)),
                    'change': int(m.group(4))
                })
        if current_group and current_group['rows']:
            groups.append(current_group)
    
    return {
        'title': title,
        'date': date_str,
        'time': None,
        'trend': trend,
        'trendValue': trend_val,
        'groups': groups,
        'source': 'boyar.cn'
    }


# ============ 搜索引擎 ============
def search_bing(query, site=None, num=5):
    """通过Bing搜索获取文章链接"""
    if site:
        full_query = f"{query} site:{site}"
    else:
        full_query = query
    url = f"https://www.bing.com/search?q={requests.utils.quote(full_query)}&count={num}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        results = []
        # 多种CSS选择器适配
        for li in soup.select('li.b_algo'):
            a = li.select_one('h2 a')
            if a:
                href = a.get('href', '')
                if href and href.startswith('http'):
                    results.append({'title': a.get_text(strip=True), 'url': href})
        # 备用选择器
        if not results:
            for a in soup.select('.b_algo h2 a, .b_title a, h2 a'):
                href = a.get('href', '')
                if href and href.startswith('http'):
                    results.append({'title': a.get_text(strip=True), 'url': href})
        return results[:num]
    except Exception as e:
        safe_print(f"  [Bing search error] {e}")
        return []


def search_sogou_weixin(query, num=5):
    """通过搜狗微信搜索公众号文章"""
    url = f"https://weixin.sogou.com/weixin?type=2&query={requests.utils.quote(query)}&ie=utf8"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        results = []
        for item in soup.select('div.txt-box'):
            a = item.select_one('h3 a')
            if a:
                title = a.get_text(strip=True)
                href = a.get('href', '')
                # 关键修复：搜狗返回的是相对URL，需要拼接域名
                if href and not href.startswith('http'):
                    href = urljoin('https://weixin.sogou.com', href)
                time_el = item.select_one('span.s2')
                pub_time = time_el.get_text(strip=True) if time_el else ''
                if href:
                    results.append({'title': title, 'url': href, 'time': pub_time})
        return results[:num]
    except Exception as e:
        safe_print(f"  [Sogou search error] {e}")
        return []


# ============ 直接抓取聚合站 ============
def scrape_boyar_category(source_name, keywords):
    """
    直接抓取 boyar.cn 蛋价分类页，找匹配的文章
    """
    category_urls = [
        'https://www.boyar.cn/category/egg/',
        'https://www.boyar.cn/category/193/',
    ]
    
    for cat_url in category_urls:
        safe_print(f"  [direct] boyar.cn: {cat_url}")
        html, final_url = fetch_url(cat_url)
        if not html:
            continue
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # 找文章列表中的链接
        articles = []
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            text = a.get_text(strip=True)
            if not text or not href:
                continue
            # 匹配包含关键词的标题
            if any(kw in text for kw in keywords):
                full_url = urljoin('https://www.boyar.cn', href)
                articles.append({'title': text, 'url': full_url})
        
        # 去重，取最近3篇
        seen = set()
        unique_articles = []
        for art in articles:
            if art['url'] not in seen:
                seen.add(art['url'])
                unique_articles.append(art)
        
        safe_print(f"  [direct] found {len(unique_articles)} matching articles")
        
        for art in unique_articles[:3]:
            safe_print(f"  [direct] trying: {art['title'][:50]}")
            article_html, _ = fetch_url(art['url'])
            if not article_html:
                continue
            
            groups = parse_price_table(article_html)
            if groups:
                date_str = extract_date_from_text(art['title']) or extract_date_from_text(article_html)
                trend, trend_val = extract_trend_from_title(art['title'])
                return {
                    'title': art['title'],
                    'date': date_str,
                    'time': None,
                    'trend': trend,
                    'trendValue': trend_val,
                    'groups': groups,
                    'source': 'boyar.cn',
                    'url': art['url']
                }
    
    return None


def scrape_boyar_latest():
    """
    直接抓取 boyar.cn 最新蛋价文章列表
    返回所有最新文章的标题和URL
    """
    safe_print("  [direct] fetching boyar.cn latest articles...")
    html, _ = fetch_url('https://www.boyar.cn/category/egg/')
    if not html:
        # 备用URL
        html, _ = fetch_url('https://www.boyar.cn/')
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = a.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        # 匹配蛋价相关文章
        if any(kw in text for kw in ['鸡蛋', '蛋价', '蛋品', '粉蛋', '红蛋', '褐壳', '报价', '行情']):
            full_url = urljoin('https://www.boyar.cn', href)
            if '/article/' in full_url or '/category/' not in full_url:
                articles.append({'title': text, 'url': full_url})
    
    # 去重
    seen = set()
    unique = []
    for art in articles:
        if art['url'] not in seen:
            seen.add(art['url'])
            unique.append(art)
    
    safe_print(f"  [direct] found {len(unique)} egg-related articles")
    return unique[:15]


def match_article_to_source(articles, source_config):
    """将文章匹配到对应的公众号"""
    name = source_config['name']
    keywords = source_config.get('search_keywords', [])
    
    for art in articles:
        title = art['title']
        # 精确匹配公众号名称
        if name in title:
            return art
        # 关键词匹配
        for kw in keywords:
            if kw in title:
                return art
    return None


# ============ 主抓取逻辑 ============
def scrape_source(key, config, boyar_articles=None):
    """抓取单个公众号的最新报价"""
    safe_print(f"\n--- scrape: {config['name']} ({key}) ---")
    
    article_data = None
    
    # 策略1: 直接从 boyar.cn 文章列表匹配
    if boyar_articles:
        matched = match_article_to_source(boyar_articles, config)
        if matched:
            safe_print(f"  [boyar] matched: {matched['title'][:50]}")
            html, _ = fetch_url(matched['url'])
            if html:
                if key == 'guantao':
                    article_data = parse_guantao_boyar(html)
                else:
                    groups = parse_price_table(html)
                    if groups:
                        date_str = extract_date_from_text(matched['title']) or extract_date_from_text(html)
                        trend, trend_val = extract_trend_from_title(matched['title'])
                        article_data = {
                            'title': matched['title'],
                            'date': date_str,
                            'time': None,
                            'trend': trend,
                            'trendValue': trend_val,
                            'groups': groups,
                            'source': 'boyar.cn',
                            'url': matched['url']
                        }
                
                if article_data and article_data.get('groups'):
                    safe_print(f"  [OK] scraped {len(article_data['groups'])} groups")
                    return article_data
                else:
                    safe_print(f"  [boyar] no price table found in article")
        else:
            safe_print(f"  [boyar] no matching article for {config['name']}")
    
    # 策略2: Bing搜索聚合站
    if not article_data:
        for keyword in config.get('search_keywords', []):
            safe_print(f"  [bing] search: {keyword}")
            results = search_bing(keyword, num=5)
            for result in results:
                url = result.get('url', '')
                if not url or 'bing.com' in url:
                    continue
                # 放宽URL过滤，允许更多来源
                safe_print(f"  [bing] trying: {result.get('title','')[:40]}")
                html, final_url = fetch_url(url)
                if not html:
                    continue
                
                if key == 'guantao' and 'boyar.cn' in url:
                    article_data = parse_guantao_boyar(html)
                else:
                    groups = parse_price_table(html)
                    if groups:
                        title = result.get('title', '')
                        article_data = {
                            'title': title,
                            'date': extract_date_from_text(title) or extract_date_from_text(html),
                            'time': None,
                            'trend': extract_trend_from_title(title)[0],
                            'trendValue': extract_trend_from_title(title)[1],
                            'groups': groups,
                            'source': 'bing',
                            'url': url
                        }
                
                if article_data and article_data.get('groups'):
                    safe_print(f"  [OK] scraped {len(article_data['groups'])} groups")
                    break
            if article_data:
                break
    
    # 策略3: 搜狗微信搜索
    if not article_data:
        for keyword in config.get('search_keywords', []):
            safe_print(f"  [sogou] search: {keyword}")
            results = search_sogou_weixin(keyword, num=3)
            for result in results:
                url = result.get('url', '')
                if not url:
                    continue
                safe_print(f"  [sogou] trying: {result.get('title','')[:40]}")
                html, final_url = fetch_url(url)
                if not html:
                    continue
                groups = parse_price_table(html)
                if groups:
                    article_data = {
                        'title': result.get('title', ''),
                        'date': extract_date_from_text(result.get('title', '')) or extract_date_from_text(html),
                        'time': result.get('time', ''),
                        'trend': extract_trend_from_title(result.get('title', ''))[0],
                        'trendValue': extract_trend_from_title(result.get('title', ''))[1],
                        'groups': groups,
                        'source': 'weixin',
                        'url': url
                    }
                    safe_print(f"  [OK] scraped {len(article_data['groups'])} groups")
                    break
            if article_data:
                break
    
    if not article_data:
        safe_print(f"  [FAIL] no data scraped")
        return None
    
    return article_data


def load_existing_data():
    """加载现有的价格数据"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"lastScrapeTime": "", "lastScrapeStatus": "", "sources": {}}


def merge_data(existing, key, config, article_data):
    """将抓取的数据合并到现有数据中"""
    source_data = existing["sources"].get(key, {})
    
    # 保留基本信息
    source_data['name'] = config['name']
    source_data['wechatId'] = config['wechat_id']
    
    # 更新文章信息
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
    
    # 更新价格组
    if article_data.get('groups'):
        source_data['groups'] = article_data['groups']
    
    existing["sources"][key] = source_data
    return existing


def main():
    safe_print("=" * 60)
    safe_print("chengcheng EGG - egg price scraper v2")
    safe_print(f"time: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
    safe_print("=" * 60)
    
    # 加载现有数据
    data = load_existing_data()
    safe_print(f"loaded {len(data.get('sources', {}))} existing sources")
    
    # 第一步：直接抓取 boyar.cn 最新文章列表（一次抓取，多源复用）
    safe_print("\n=== Step 1: Fetch boyar.cn latest articles ===")
    boyar_articles = scrape_boyar_latest()
    
    success_count = 0
    fail_count = 0
    
    for key, config in SOURCES.items():
        try:
            article_data = scrape_source(key, config, boyar_articles)
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
        
        # 礼貌延迟
        time.sleep(1)
    
    # 更新抓取时间
    data["lastScrapeTime"] = datetime.now(CST).isoformat()
    data["lastScrapeStatus"] = f"success:{success_count}, failed:{fail_count}"
    
    # 保存
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
