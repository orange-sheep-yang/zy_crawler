import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import re

# 目标网站URL
TARGET_URL = "https://kxjst.jiangsu.gov.cn/col/col82571/index.html"
SOURCE_NAME = "江苏省科学技术厅_政策文件"

# ==========================================
# 1. 网页抓取逻辑
# ==========================================
def scrape_data():
    """抓取数据，返回与表结构一致的字典列表"""
    policies = []
    all_items = 0
    
    try:
        # 计算前一天日期（使用北京时间 UTC+8）
        tz_utc8 = timezone(timedelta(hours=8))
        today = datetime.now(tz_utc8).date()
        yesterday = today - timedelta(days=1)
        
        # 请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        }
        
        # 请求页面
        response = requests.get(TARGET_URL, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 直接提取所有 a 标签（这个页面是纯静态列表）
        a_list = soup.select("a[href*='/art/']")
        all_items = len(a_list)
        print(f"📋 找到 {all_items} 条政策文件")
        
        target_date_items = 0
        non_target_date_items = 0
        
        for a_tag in a_list:
            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "").strip()
            date_text = a_tag.next_sibling.strip() if a_tag.next_sibling else ""
            
            # 提取日期
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
            if not date_match:
                continue
            date_str = date_match.group(1)
            
            # 解析日期
            try:
                pub_at = datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                continue
            
            # 只保留昨天的
            if pub_at != yesterday:
                non_target_date_items += 1
                continue
            
            # 处理URL
            if not href.startswith('http'):
                href = f"https://kxjst.jiangsu.gov.cn{href}"
            
            # 抓取正文
            content = ""
            try:
                resp = requests.get(href, headers=headers, timeout=15)
                resp.raise_for_status()
                ds = BeautifulSoup(resp.text, 'html.parser')
                content_elem = ds.select_one('.main-txt') or ds.select_one('#zoom')
                if content_elem:
                    content = content_elem.get_text(strip=True)
                    content = re.sub(r'来源：.*?$', '', content, flags=re.DOTALL).strip()
            except Exception as e:
                print(f"⚠️  抓取详情失败：{href} | {e}")
            
            policy_data = {
                'title': title,
                'url': href,
                'pub_at': pub_at,
                'content': content,
                'selected': False,
                'category': '江苏省科技厅政策文件',
                'source': SOURCE_NAME
            }
            policies.append(policy_data)
            target_date_items += 1
        
        print(f"✅ 成功抓取昨日数据：{target_date_items} 条")
        print(f"⏭️  过滤非昨日数据：{non_target_date_items} 条")
        
        # 打印最新5条
        print("\n📊 页面最新5条：")
        for i, a in enumerate(a_list[:5]):
            t = a.get_text(strip=True)
            d = a.next_sibling.strip() if a.next_sibling else ""
            print(f"✅ {t} {d}")
        
    except Exception as e:
        print(f"❌ 抓取失败：{e}")
    
    return policies, all_items

# ==========================================
# 2. 数据入库逻辑
# ==========================================
def save_to_supabase(data_list):
    try:
        from db_utils import save_to_policy
        return save_to_policy(data_list, SOURCE_NAME)
    except Exception:
        return data_list

# ==========================================
# 3. 主函数
# ==========================================
def run():
    try:
        data, all_items = scrape_data()
        if data:
            result, api_push_result = save_to_supabase(data)
            print(f"\n💾 写入数据库：{len(result)} 条")
            return result
        else:
            print("\n💾 写入数据库：0 条")
            print("⚠️  未找到昨日发布的政策文件")
            return []
    except Exception as e:
        print(f"❌ 爬虫运行失败：{e}")
        return []

# ==========================================
# 主入口
# ==========================================
if __name__ == "__main__":
    run()
