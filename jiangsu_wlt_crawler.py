import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

# 导入数据库工具
from db_utils import save_to_policy

# ==========================================
# 1. 终极配置：双栏目抓取
# ==========================================
TARGETS = [
    {
        "name": "江苏省文旅厅_焦点新闻", 
        "columnid": "695", 
        "unitid": "423807", 
        "base_url": "https://wlt.jiangsu.gov.cn/col/col695/index.html"
    },
    {
        "name": "江苏省文旅厅_通知公告", 
        "columnid": "699", 
        "unitid": "423807", # ✅ 已经帮你填好了刚刚找到的暗号
        "base_url": "https://wlt.jiangsu.gov.cn/col/col699/index.html"
    }
]

# Hanweb 系统的标准数据请求接口
PROXY_URL = "https://wlt.jiangsu.gov.cn/module/web/jpage/dataproxy.jsp"

def scrape_data():
    policies = []
    all_items = []
    
    # 获取北京时间昨天日期
    tz_utc8 = timezone(timedelta(hours=8))
    yesterday = (datetime.now(tz_utc8) - timedelta(days=1)).date()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }

    for target in TARGETS:
        # 防呆设计：如果没有填unitid，直接跳过提示
        if not target["unitid"].isdigit():
            print(f"⚠️ {target['name']} 跳过：请先在代码里填入正确的 unitid！")
            continue

        print(f"🔍 正在请求接口: {target['name']}")
        
        params = {
            'page': 1,
            'appid': 1,
            'webid': 12,
            'path': '/',
            'columnid': target['columnid'],
            'unitid': target['unitid'],
            'permissiontype': 0
        }
        
        try:
            response = requests.get(PROXY_URL, params=params, headers=headers, timeout=30)
            response.encoding = 'utf-8'
            
            records = re.findall(r'<record><!\[CDATA\[([\s\S]*?)\]\]></record>', response.text)
            
            for record_html in records:
                soup_item = BeautifulSoup(record_html, 'html.parser')
                a_tag = soup_item.find('a')
                date_match = re.search(r'202\d-\d{2}-\d{2}', record_html)
                
                if a_tag and date_match:
                    title = a_tag.get('title') or a_tag.get_text(strip=True)
                    href = a_tag.get('href')
                    link = urljoin(target["base_url"], href)
                    pub_at = datetime.strptime(date_match.group(), '%Y-%m-%d').date()
                    
                    item_info = {'title': title, 'pub_at': pub_at, 'url': link}
                    if item_info not in all_items:
                        all_items.append(item_info)

                    # ========================================================
                    # 🚀 放水测试开关：已改为 if True 强制抓取，无视日期限制
                    # ========================================================
                    if True: 
                        print(f"✨ [测试模式] 发现文章: {title} ({pub_at})")
                        content = ""
                        try:
                            detail_res = requests.get(link, headers=headers, timeout=20)
                            detail_res.encoding = 'utf-8'
                            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                            
                            content_elem = detail_soup.select_one('#UCAP-CONTENT') or detail_soup.select_one('.bt-content')
                            if content_elem:
                                content = content_elem.get_text(strip=True)
                                print(f"   └─ 成功抓取正文，字数：{len(content)}")
                        except Exception as e:
                            print(f"⚠️ 详情页抓取失败 {link}: {e}")

                        category_name = target["name"].split('_')[1]
                        policies.append({
                            'title': title,
                            'url': link,
                            'pub_at': pub_at,
                            'content': content,
                            'source': '江苏省文旅厅',
                            'category': category_name
                        })

                        # 【安全阀】：统计当前栏目抓了几条，达到 2 条立刻停止当前栏目的抓取
                        current_category_count = sum(1 for p in policies if p['category'] == category_name)
                        if current_category_count >= 2:
                            print(f"🛑 [测试安全阀] {target['name']} 已抓满 2 条，强制进入下一栏目！")
                            break # 跳出当前栏目的循环

        except Exception as e:
            print(f"❌ {target['name']} 接口访问失败: {e}")

    print(f"✅ 江苏省文旅厅本次收集到 {len(policies)} 条待入库数据")
    return policies, all_items

def run():
    try:
        data, all_items = scrape_data()
        
        if all_items:
            print("📊 页面最新抓取记录是：")
            for i, item in enumerate(all_items[:8], 1):
                print(f"✅ [{item['pub_at']}] {item['title']}")
        
        if data:
            save_to_policy(data, "江苏省文旅厅")
            print(f"💾 写入数据库: {len(data)} 条")
            return data
        else:
            print("💾 写入数据库: 0 条 (没有符合日期的数据)")
            return []
            
    except Exception as e:
        print(f"❌ 文旅厅爬虫运行异常: {e}")
        return []

if __name__ == "__main__":
    run()
