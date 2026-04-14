import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import re

# 配置信息
TARGET_URL = "https://scjgj.jiangsu.gov.cn/col/col78964/index.html"
SOURCE_NAME = "江苏省市场监督管理局_政策文件"

def scrape_data():
    """抓取昨日更新的政策数据"""
    policies = []
    all_items = 0
    
    try:
        # 1. 时间设定：仅限昨日数据
        tz_utc8 = timezone(timedelta(hours=8))
        today = datetime.now(tz_utc8).date()
        yesterday = today - timedelta(days=1)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        # 2. 访问列表页
        response = requests.get(TARGET_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        datastore_script = next((s.string for s in soup.find_all('script') if s.string and '<datastore>' in s.string), None)
        
        if not datastore_script:
            return policies, 0
        
        records = re.findall(r'<record><!\[CDATA\[(.*?)\]\]></record>', datastore_script, re.DOTALL)
        all_items = len(records)
        
        # 3. 循环解析记录
        for record in records:
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', record)
            if not date_match: continue
            
            pub_at = datetime.strptime(date_match.group(1), '%Y-%m-%d').date()
            
            # 【核心逻辑】仅处理昨天的数据
            if pub_at == yesterday:
                title = re.search(r'title=(["\'])(.*?)\1', record).group(2)
                url = re.search(r'href=(["\'])(.*?)\1', record).group(2)
                if not url.startswith('http'):
                    url = f"https://scjgj.jiangsu.gov.cn{url}"

                # 抓取详情页
                content = ""
                try:
                    d_res = requests.get(url, headers=headers, timeout=15)
                    d_res.encoding = d_res.apparent_encoding
                    d_soup = BeautifulSoup(d_res.content, 'html.parser')
                    c_elem = d_soup.select_one('.main-txt')
                    if c_elem:
                        # 清理无关干扰
                        for extra in c_elem.select('script, style, .newnewerm, .ie8sys'):
                            extra.decompose()
                        content = c_elem.get_text(strip=True)
                except Exception as e:
                    print(f"⚠️ 详情抓取失败: {url} - {e}")

                policies.append({
                    'title': title,
                    'url': url,
                    'pub_at': pub_at,
                    'content': content,
                    'selected': False,
                    'category': '',
                    'source': SOURCE_NAME
                })
                
        print(f"✅ [{SOURCE_NAME}]：解析完成，昨日新增 {len(policies)} 条")
        
    except Exception as e:
        print(f"❌ [{SOURCE_NAME}] 运行失败: {e}")
    
    return policies, all_items

def save_to_supabase(data_list):
    """保存到数据库"""
    try:
        from db_utils import save_to_policy
        return save_to_policy(data_list, SOURCE_NAME)
    except ImportError:
        return data_list, None

def run():
    data, _ = scrape_data()
    if data:
        result, _ = save_to_supabase(data)
        print(f"💾 写入数据库: {len(result)} 条")
        return result
    else:
        print("💾 今日无昨日日期数据更新")
        return []

if __name__ == "__main__":
    run()
