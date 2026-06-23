#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
乘乘EGG · 全国鸡蛋价格看板 - 自动爬虫
从多个公开渠道抓取12个公众号的最新鸡蛋报价，输出到 data/prices.json
"""

import json
import re
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

# ============ 配置 ============
CST = timezone(timedelta(hours=8))
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'prices.json')

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
        "aggregation_sites": ["boyar.cn", "163.com", "sohu.com"],
    },
    "jiameixian": {
        "name": "家美鲜鸡蛋",
        "wechat_id": "XSJMXJD",
        "search_keywords": ["家美鲜鸡蛋 价格", "佳美鲜 鸡蛋报价"],
        "aggregation_sites": ["boyar.cn", "163.com", "sohu.com"],
    },
    "sanjian": {
        "name": "湖南三尖农牧公司",
        "wechat_id": "hnsjnm",
        "search_keywords": ["湖南三尖农牧 鸡蛋", "三尖农牧 蛋价"],
        "aggregation_sites": ["boyar.cn", "163.com"],
    },
    "xiji": {
        "name": "河北辛集城方蛋品",
        "wechat_id": "gh_8860042e77c8",
        "search_keywords": ["辛集 蛋品 价格", "河北辛集 鸡蛋报价"],
        "aggregation_sites": ["boyar.cn", "163.com"],
    },
    "jiujiang": {
        "name": "江西九江褐壳蛋",
        "wechat_id": "gh_6e1164286ce7",
        "search_keywords": ["九江 褐壳蛋 价格", "江西九江 鸡蛋报价"],
        "aggregation_sites": ["boyar.cn", "163.com"],
    },
    "jingugu": {
        "name": "河南金咕咕蛋品",
        "wechat_id": "W13253661972",
        "search_keywords": ["金咕咕 蛋品 价格", "河南金咕咕 鸡蛋"],
        "aggregation_sites": ["boyar.cn", "163.com"],
    },
    "lantian": {
        "name": "蓝天禽蛋联盟",
        "wechat_id": "gh_be44b3efceb2",
        "search_keywords": ["蓝天禽蛋联盟 北京 鸡蛋", "蓝天禽蛋 鸡蛋价格"],
        "aggregation_sites": ["boyar.cn", "163.com"],
    },
    "xinzhou": {
        "name": "武汉市新洲区兄弟蛋业",
        "wechat_id": "xiongdidanye666",
        "search_keywords": ["兄弟蛋业 绿壳蛋", "武汉新洲 鸡蛋报价"],
        "aggregation_sites": ["boyar.cn", "163.com"],
    },
    "guiyang": {
        "name": "贵阳鸡蛋价格",
        "wechat_id": "gh_ea5f7cbced8d",
        "search_keywords": ["贵阳鸡蛋价格", "贵州贵阳 鸡蛋报价"],
        "aggregation_sites": ["boyar.cn", "163.com"],
    },
    "jingyao": {
        "name": "河北京饶蛋品",
        "wechat_id": "hebeijingraodanpin",
        "search_keywords": ["京饶蛋品 价格", "河北饶阳 鸡蛋报价"],
        "aggregation_sites": ["boyar.cn", "163.com"],
    },
    "jinlong": {
        "name": "晋龙饲料",
        "wechat_id": "jinlongsiliao",
        "search_keywords": ["晋龙饲料 鸡蛋价格", "山西晋龙 蛋价"],
        "aggregation_sites": ["boyar.cn", "163.com"],
    },
    "zhuochuang": {
        "name": "卓创资讯订阅号",
        "wechat_id": "sci-99",
        "search_keywords": ["卓创资讯 鸡蛋价格", "卓创 鸡蛋行情"],
        "aggregation_sites": ["boyar.cn", "163.com", "sci99.com"],
    },
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
        for li in soup.select('li.b_algo'):
            a = li.select_one('h2 a')
            if a:
                results.append({
                    'title': a.get_text(strip=True),
                    'url': a.get('href', ''),
                })
        return results
    except Exception as e:
        print(f"  [Bing搜索失败] {e}")
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
                # 获取发布时间
                time_el = item.select_one('span.s2')
                pub_time = time_el.get_text(strip=True) if time_el else ''
                results.append({
                    'title': title,
                    'url': href,
                    'time': pub_time,
                })
        return results
    except Exception as e:
        print(f"  [搜狗微信搜索失败] {e}")
        return []


# ============ 文章抓取 ============
def fetch_url(url):
    """抓取URL内容"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        return resp.text
    except Exception as e:
        print(f"  [抓取失败] {url}: {e}")
        return None


# ============ 通用解析器 ============
def extract_date_from_text(text):
    """从文本中提取日期"""
    # 匹配 "2026年6月22日" 或 "6月22日"
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
    m = re.search(r'(\d{1,2}):(\d{2})', text)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def extract_trend_from_title(title):
    """从标题提取涨跌趋势"""
    if not title:
        return None, None
    if '跌' in title or '降' in title or '落' in title:
        return '跌', -1
    if '涨' in title or '升' in title:
        return '涨', 1
    if '稳' in title or '平' in title:
        return '稳', 0
    return None, None


def parse_price_table(html_text, source_name):
    """
    通用价格表解析器
    从HTML文本中提取价格表格数据
    """
    soup = BeautifulSoup(html_text, 'html.parser')
    groups = []
    
    # 策略1: 查找 <table> 标签
    tables = soup.find_all('table')
    for table in tables:
        rows_data = parse_table_element(table)
        if rows_data and len(rows_data) > 0:
            groups.append({
                'name': '',
                'rows': rows_data
            })
    
    # 策略2: 查找文本中的价格行模式
    if not groups:
        text = soup.get_text()
        rows_data = parse_price_lines_from_text(text)
        if rows_data:
            groups.append({
                'name': '',
                'rows': rows_data
            })
    
    return groups


def parse_table_element(table):
    """解析 <table> 元素"""
    rows = []
    for tr in table.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        if len(cells) < 3:
            continue
        cell_texts = [c.get_text(strip=True) for c in cells]
        
        # 跳过表头
        if '规格' in cell_texts[0] or '品种' in cell_texts[0] or '净重' in cell_texts[0]:
            continue
        
        spec = cell_texts[0]
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
    # 匹配 "45斤 192 188 -4" 或 "45斤 192元 188元 -4" 这样的行
    pattern = r'(\d+[-–—]\d+斤|\d+斤|[^\d\n]{2,10})\s+(\d+)\s*元?\s+(\d+)\s*元?\s*([-+]\d+|[-−]\d+)'
    for m in re.finditer(pattern, text):
        spec = m.group(1).strip()
        yesterday = int(m.group(2))
        today = int(m.group(3))
        change_str = m.group(4).replace('−', '-').replace('−', '-')
        change = int(change_str)
        rows.append({
            'spec': spec,
            'yesterday': yesterday,
            'today': today,
            'change': change
        })
    return rows


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
    text = text.replace('−', '-').replace('—', '-').replace('－', '-')
    # 匹配 -4, +3, ▼3, ▲3, 跌4, 涨3
    m = re.search(r'([-+]\d+)', text)
    if m:
        return int(m.group(1))
    if '持平' in text or '稳' in text or '平' in text:
        return 0
    m = re.search(r'[▼跌降落](\d+)', text)
    if m:
        return -int(m.group(1))
    m = re.search(r'[▲涨升](\d+)', text)
    if m:
        return int(m.group(1))
    return None


# ============ 馆陶专用解析器 ============
def parse_guantao_boyar(html_text):
    """解析 boyar.cn 上的馆陶鸡蛋报价文章"""
    soup = BeautifulSoup(html_text, 'html.parser')
    text = soup.get_text()
    
    # 提取标题
    title = ''
    title_el = soup.find('h1') or soup.find('title')
    if title_el:
        title = title_el.get_text(strip=True)
    
    # 提取日期
    date_str = extract_date_from_text(title) or extract_date_from_text(text)
    
    # 提取趋势
    trend, trend_val = extract_trend_from_title(title)
    
    # 查找表格数据
    groups = []
    
    # boyar.cn 的格式: 净重/昨日价/今日价/涨跌 在表格中
    tables = soup.find_all('table')
    current_group_name = ''
    
    for table in tables:
        rows_data = parse_table_element(table)
        if rows_data:
            groups.append({
                'name': current_group_name,
                'rows': rows_data
            })
    
    # 如果没有表格，尝试从文本解析
    if not groups:
        # boyar.cn 的文本格式: "45斤 192元 188元 -4"
        lines = text.split('\n')
        current_group = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 检测分组标题
            if '蛋托' in line or '精品' in line or '草绿' in line:
                if current_group and current_group['rows']:
                    groups.append(current_group)
                current_group = {'name': line, 'rows': []}
                continue
            # 解析价格行
            m = re.match(r'(\d+[-–—]\d+斤|\d+斤)\s+(\d+)元?\s+(\d+)元?\s*([-+]?-?\d+)', line)
            if m and current_group is not None:
                current_group['rows'].append({
                    'spec': m.group(1),
                    'yesterday': int(m.group(2)),
                    'today': int(m.group(3)),
                    'change': int(m.group(4).replace('-', '-'))
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


# ============ 主抓取逻辑 ============
def scrape_source(key, config):
    """抓取单个公众号的最新报价"""
    print(f"\n--- 抓取: {config['name']} ({key}) ---")
    
    article_data = None
    
    # 策略1: 在聚合站搜索
    for site in config.get('aggregation_sites', []):
        for keyword in config.get('search_keywords', []):
            print(f"  搜索 {site}: {keyword}")
            results = search_bing(keyword, site=site, num=3)
            for result in results:
                url = result['url']
                if not url or 'boyar.cn' not in url and '163.com' not in url and 'sohu.com' not in url:
                    continue
                
                print(f"  尝试: {result['title'][:40]}...")
                html = fetch_url(url)
                if not html:
                    continue
                
                # 使用对应解析器
                if key == 'guantao' and 'boyar.cn' in url:
                    article_data = parse_guantao_boyar(html)
                else:
                    groups = parse_price_table(html, config['name'])
                    if groups:
                        title = result.get('title', '')
                        article_data = {
                            'title': title,
                            'date': extract_date_from_text(title) or extract_date_from_text(html),
                            'time': None,
                            'trend': extract_trend_from_title(title)[0],
                            'trendValue': extract_trend_from_title(title)[1],
                            'groups': groups,
                            'source': site
                        }
                
                if article_data and article_data.get('groups'):
                    article_data['url'] = url
                    print(f"  ✓ 成功抓取 ({len(article_data['groups'])} 组数据)")
                    break
            
            if article_data:
                break
        if article_data:
            break
    
    # 策略2: 搜狗微信搜索
    if not article_data:
        for keyword in config.get('search_keywords', []):
            print(f"  搜狗微信搜索: {keyword}")
            results = search_sogou_weixin(keyword, num=3)
            for result in results:
                url = result.get('url', '')
                if not url:
                    continue
                print(f"  尝试: {result.get('title', '')[:40]}...")
                html = fetch_url(url)
                if not html:
                    continue
                groups = parse_price_table(html, config['name'])
                if groups:
                    article_data = {
                        'title': result.get('title', ''),
                        'date': extract_date_from_text(result.get('title', '')) or result.get('time', ''),
                        'time': result.get('time', ''),
                        'trend': extract_trend_from_title(result.get('title', ''))[0],
                        'trendValue': extract_trend_from_title(result.get('title', ''))[1],
                        'groups': groups,
                        'source': 'weixin',
                        'url': url
                    }
                    print(f"  ✓ 成功抓取 ({len(article_data['groups'])} 组数据)")
                    break
            if article_data:
                break
    
    # 策略3: Bing通用搜索
    if not article_data:
        for keyword in config.get('search_keywords', []):
            print(f"  Bing通用搜索: {keyword}")
            results = search_bing(keyword, num=5)
            for result in results:
                url = result.get('url', '')
                if not url or 'bing.com' in url:
                    continue
                print(f"  尝试: {result.get('title', '')[:40]}...")
                html = fetch_url(url)
                if not html:
                    continue
                groups = parse_price_table(html, config['name'])
                if groups:
                    article_data = {
                        'title': result.get('title', ''),
                        'date': extract_date_from_text(result.get('title', '')),
                        'time': None,
                        'trend': extract_trend_from_title(result.get('title', ''))[0],
                        'trendValue': extract_trend_from_title(result.get('title', ''))[1],
                        'groups': groups,
                        'source': 'web',
                        'url': url
                    }
                    print(f"  ✓ 成功抓取 ({len(article_data['groups'])} 组数据)")
                    break
            if article_data:
                break
    
    if not article_data:
        print(f"  ✗ 未能抓取到数据")
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
        'time': article_data.get('time', ''),
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
    print("=" * 60)
    print("乘乘EGG · 鸡蛋价格爬虫启动")
    print(f"时间: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 加载现有数据
    data = load_existing_data()
    print(f"已加载 {len(data.get('sources', {}))} 个数据源")
    
    success_count = 0
    fail_count = 0
    
    for key, config in SOURCES.items():
        try:
            article_data = scrape_source(key, config)
            if article_data:
                data = merge_data(data, key, config, article_data)
                success_count += 1
            else:
                fail_count += 1
                # 保留现有数据，标记为pending
                if key in data["sources"]:
                    data["sources"][key]['status'] = 'pending'
        except Exception as e:
            print(f"  [异常] {key}: {e}")
            fail_count += 1
        
        # 礼貌延迟，避免被封
        time.sleep(2)
    
    # 更新抓取时间
    data["lastScrapeTime"] = datetime.now(CST).isoformat()
    data["lastScrapeStatus"] = f"success:{success_count}, failed:{fail_count}"
    
    # 保存
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print(f"抓取完成: 成功 {success_count}, 失败 {fail_count}")
    print(f"数据已保存到: {DATA_FILE}")
    print(f"时间: {data['lastScrapeTime']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
