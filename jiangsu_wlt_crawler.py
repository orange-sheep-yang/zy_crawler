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
        "unitid": "423807", 
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
            
            filtered_count = 0

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

                    # 严格日期判断逻辑：只抓昨天的数据
                    if pub_at == yesterday: 
                        content = ""
                        try:
                            detail_res = requests.get(link, headers=headers, timeout=20)
                            detail_res.encoding = 'utf-8'
                            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                            
                            content_elem = detail_soup.select_one('#UCAP-CONTENT') or detail_soup.select_one('.bt-content')
                            if content_elem:
                                content = content_elem.get_text(strip=True)
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
                    else:
                        filtered_count += 1
                        
            print(f"⏭️  {target['name']}：过滤掉 {filtered_count} 条非目标日期的数据")

        except Exception as e:
            print(f"❌ {target['name']} 接口访问失败: {e}")

    print(f"✅ 江苏省文旅厅爬虫：成功抓取 {len(policies)} 条前一天数据")
    
    # 打印页面最新5条（格式与其他爬虫完全一致）
    if all_items:
        print("📊 页面最新5条是：")
        for i, item in enumerate(all_items[:5], 1):
            date_str = item['pub_at'].strftime('%Y-%m-%d') if item['pub_at'] else '未知日期'
            print(f"✅ {item['title']} {date_str}")
            
    return policies, all_items

def run():
    try:
        data, _ = scrape_data()
        
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
