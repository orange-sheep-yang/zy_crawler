import os
import re
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

# 导入数据库工具
from db_utils import save_to_policy

# ==========================================
# 1. 配置：改用数据接口 URL
# ==========================================
# 这里的 URL 后面带的 colid 就是原网页 col694, col695 等数字
TARGETS = [
    {"name": "江苏省文旅厅_文旅资讯", "colid": "694", "base_url": "https://wlt.jiangsu.gov.cn/col/col694/index.html"},
    {"name": "江苏省文旅厅_焦点新闻", "colid": "695", "base_url": "https://wlt.jiangsu.gov.cn/col/col695/index.html"},
    {"name": "江苏省文旅厅_通知公告", "colid": "699", "base_url": "https://wlt.jiangsu.gov.cn/col/col699/index.html"}
]

# 统一的数据接口地址模板
PROXY_URL_TEMPLATE = "https://wlt.jiangsu.gov.cn/module/web/jpage/dataproxy.jsp?startrecord=1&endrecord=40&perpage=20&colid={colid}"

def scrape_data():
    policies = []
    all_items = []
    
    # 时区处理
    tz_utc8 = timezone(timedelta(hours=8))
    today = datetime.now(tz_utc8).date()
    yesterday = today - timedelta(days=1)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }

    for target in TARGETS:
        proxy_url = PROXY_URL_TEMPLATE.format(colid=target["colid"])
        print(f"🔍 正在通过接口抓取: {target['name']}")
        
        try:
            # 1. 请求数据接口（通常接口不会有 521 拦截）
            response = requests.get(proxy_url, headers=headers, timeout=30)
            response.encoding = 'utf-8'
            
            # 2. 接口返回的是 XML 包装的 HTML 片段，使用正则提取记录
            # 模仿农业农村厅的 recordset 解析逻辑
            records = re.findall(r'<record><!\[CDATA\[([\s\S]*?)\]\]></record>', response.text)
            
            for record_html in records:
                soup_item = BeautifulSoup(record_html, 'html.parser')
                a_tag = soup_item.find('a')
                
                # 提取日期（通常在 span 或 i 标签中，或直接在文本里）
                date_match = re.search(r'202\d-\d{2}-\d{2}', record_html)
                
                if a_tag and date_match:
                    title = a_tag.get('title') or a_tag.get_text(strip=True)
                    href = a_tag.get('href')
                    link = urljoin(target["base_url"], href)
                    pub_at = datetime.strptime(date_match.group(), '%Y-%m-%d').date()
                    
                    item_info = {'title': title, 'pub_at': pub_at, 'url': link}
                    if item_info not in all_items:
                        all_items.append(item_info)

                    # 3. 匹配日期：如果是昨天，则进入详情页抓取正文
                    if pub_at == yesterday:
                        print(f"✨ 发现目标文章: {title}")
                        content = ""
                        try:
                            # 模仿农业农村厅：点进详情页抓取
                            detail_res = requests.get(link, headers=headers, timeout=20)
                            detail_res.encoding = 'utf-8'
                            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                            
                            # 江苏省厅网站正文容器通常是 #UCAP-CONTENT 或 .bt-content
                            content_elem = detail_soup.select_one('#UCAP-CONTENT') or detail_soup.select_one('.bt-content')
                            if content_elem:
                                content = content_elem.get_text(strip=True)
                        except Exception as e:
                            print(f"⚠️ 详情页抓取失败 {link}: {e}")

                        policies.append({
                            'title': title,
                            'url': link,
                            'pub_at': pub_at,
                            'content': content,
                            'source': '江苏省文旅厅',
                            'category': target["name"].split('_')[1]
                        })

        except Exception as e:
            print(f"❌ {target['name']} 接口访问失败: {e}")

    print(f"✅ 江苏省文旅厅总计抓取到 {len(policies)} 条昨日数据")
    return policies, all_items
    
def run():
    try:
        data, all_items = scrape_data()
        
        if all_items:
            print("📊 页面最新5条是：")
            for i, item in enumerate(all_items[:5], 1):
                print(f"✅ {item['title']} {item['pub_at']}")
        
        if data:
            save_to_policy(data, "江苏省文旅厅")
            print(f"💾 写入数据库: {len(data)} 条")
            return data  # ✅ 修复点1：成功抓到数据时，必须 return data
        else:
            print("💾 写入数据库: 0 条 (没有昨日数据)")
            return []    # ✅ 修复点2：没有抓到数据时，必须 return 一个空列表 []
            
    except Exception as e:
        print(f"❌ 文旅厅爬虫运行异常: {e}")
        return []        # ✅ 修复点3：发生异常时，也必须 return 一个空列表 []


if __name__ == "__main__":
    run()
