import requests
from bs4 import BeautifulSoup, Tag
import pandas as pd
import time
import random
import re
from urllib.parse import urljoin
import os
import json

# HTTP請求頭

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.google.com/',
}

# 網站基本URL

BASE_URL = "https://www.bnext.com.tw"

# 預設類別URL列表

DEFAULT_CATEGORIES = [
    # AI相關類別優先
    f"{BASE_URL}/categories/ai",           # AI與大數據

    # 其他可能有AI相關內容的類別
    f"{BASE_URL}/categories/tech",         # 科技總覽
    f"{BASE_URL}/categories/iot",          # 物聯網
    f"{BASE_URL}/categories/smartmedical", # 醫療生技
    f"{BASE_URL}/categories/smartcity",    # 智慧城市
    f"{BASE_URL}/categories/cloudcomputing", # 雲端運算與服務
    f"{BASE_URL}/categories/security",     # 資訊安全
    
    # 一般類別
    f"{BASE_URL}/articles",                # 最新新聞
    f"{BASE_URL}/categories/5g",           # 5G通訊
    f"{BASE_URL}/categories/car",          # 電動車／交通科技
    f"{BASE_URL}/categories/blockchain",   # 區塊鏈
    f"{BASE_URL}/categories/energy",       # 能源環保
    f"{BASE_URL}/categories/semiconductor", # 半導體與電子產業
    f"{BASE_URL}/categories/manufacture",  # 智慧製造

]

config_file_path = "/content/bnext_crawler_config.json"

if os.path.exists(config_file_path):
  with open(config_file_path, 'r', encoding='utf-8') as f:
    file_config = json.load(f)
else:
    file_config = {}  # 或其他預設值
    print(f"設定檔 {config_file_path} 不存在，使用預設設定。")

print("讀取設定檔內容：")
print(file_config)

selectors = file_config.get("selectors", None)

if not selectors:
  raise

#開始抓取
session = requests.Session()
all_articles = []

categories = DEFAULT_CATEGORIES
category_url = categories[0]

current_url = category_url + "?page=2"
print(current_url)

# 增加隨機延遲，避免被封鎖

time.sleep(random.uniform(1.5, 3.5))
response = session.get(current_url, headers=DEFAULT_HEADERS, timeout=15)

if response.status_code != 200:
  print(f"頁面請求失敗: {response.status_code}")

soup = BeautifulSoup(response.text, 'html.parser')

# 載入文本選擇器

get_article_links_selectors = selectors.get('get_article_links')
get_grid_contentainer_selector = get_article_links_selectors.get("article_grid_container")





# 提取文章連結

articles_container = soup.select(get_article_links_selectors.get("articles_container"))
if not articles_container:
    print("未找到文章容器")
    exit()

category = articles_container[0].select_one(get_article_links_selectors.get("category"))
c_text = category.get_text(strip=True) if category else None
link = articles_container[0].select_one(get_article_links_selectors.get("link"))
l_text = link.get_attribute_list('href')[0] if link else None
title = articles_container[0].select_one(get_article_links_selectors.get("title"))
t_text = title.get_text(strip=True) if title else None
summary = articles_container[0].select_one(get_article_links_selectors.get("summary"))
s_text = summary.get_text(strip=True) if summary else None
published_age = articles_container[0].select_one(get_article_links_selectors.get("published_age"))
p_text = published_age.get_text(strip=True) if published_age else None

print(f'category: {c_text}')
print(f'm-article_link: {l_text}')
print(f'm-article_title: {t_text}')
print(f'm-article_summary: {s_text}')
print(f'm-article_published_age: {p_text}')

article_grid_container = articles_container[0].select_one(get_grid_contentainer_selector.get("container"))
if not article_grid_container:
    print("未找到文章網格容器")
    exit()

for idx, container in enumerate(article_grid_container.children,1):  # 迭代直接子元素
    if isinstance(container, Tag):  # 檢查是否為 Tag 物件
        try:
            # 檢查 container 是否為 div 標籤
            if container.name != 'div':
                continue

            g_article_link = container.select_one(get_grid_contentainer_selector.get("link"))  # 修改選擇器，直接查找 a 標籤
            if g_article_link:
                g_article_link_text = g_article_link.get('href')
                print(f"第{idx}篇文章連結: {g_article_link_text}")  # 列印文章連結
    
            g_article_title = container.select_one(get_grid_contentainer_selector.get("title"))  # 修改選擇器，直接查找 h2 標籤
            if g_article_title:
                g_article_title_text = g_article_title.get_text(strip=True)
                print(f"第{idx}篇文章標題: {g_article_title_text}")  # 列印文章標題
            g_article_summary = container.select_one(get_grid_contentainer_selector.get("summary"))
            if g_article_summary:
                g_article_summary_text = g_article_summary.get_text(strip=True)
                print(f"第{idx}篇文章摘要: {g_article_summary_text}")  # 列印文章摘要
            g_articel_published_age = container.select_one(get_grid_contentainer_selector.get("published_age"))
            if g_articel_published_age:
                g_articel_published_age_text = g_articel_published_age.get_text(strip=True)
                print(f"第{idx}篇文章發佈時間: {g_articel_published_age_text}")  # 列印文章發佈時間
    
        except Exception as e:
            print(f"發生錯誤: {e}")
    else:
        # 处理非 Tag 元素，例如 NavigableString
        pass  # 或进行其他操作

# 爬取文章內容

# 增加隨機延遲，避免被封鎖
get_article_contents_selectors = selectors.get("get_article_contents")
content_url =  "https://www.bnext.com.tw/article/82749/anthropic-program-superpower"
print(content_url)
time.sleep(random.uniform(1.5, 3.5))
response = session.get(content_url, headers=DEFAULT_HEADERS, timeout=15)

if response.status_code != 200:
  print(f"頁面請求失敗: {response.status_code}")

#抓取文章內容
print("抓取文章內容")
soup = BeautifulSoup(response.text, 'html.parser')
article_content_container = soup.select(get_article_contents_selectors.get("content_container"))
if not article_content_container:
    print("未找到文章內容容器")
    exit()

print(f"找到文章內容容器數量: {len(article_content_container)}")

c_category = article_content_container[0].select_one(get_article_contents_selectors.get("category"))
c_c_text = c_category.get_text(strip=True) if c_category else None
c_published_date = article_content_container[0].select_one(get_article_contents_selectors.get("published_date"))
c_p_text = c_published_date.get_text(strip=True) if c_published_date else None
c_title = article_content_container[0].select_one(get_article_contents_selectors.get("title"))
c_t_text = c_title.get_text(strip=True) if c_title else None
c_summary  = article_content_container[0].select_one(get_article_contents_selectors.get("summary"))
c_s_text = c_summary.get_text(strip=True) if c_summary else None
print(f'category: {c_c_text}')
print(f'published_date: {c_p_text}')
print(f'title: {c_t_text}')
print(f'summary: {c_s_text}')

c_tags_container = article_content_container[0].select_one(get_article_contents_selectors.get("tags").get("container"))
if not c_tags_container:
  print("標籤容器抓取失敗")
  exit()

print(f"找到標籤容器數量: {len(c_tags_container)}")

for container in c_tags_container.children:
  if isinstance(container, Tag):
    if container.name == get_article_contents_selectors.get("tags").get("tag"):  # 檢查是否為 <a> 標籤
      c_tag_text = container.get_text(strip=True)
      print(f"找到Tag: {c_tag_text}")
    else:
      c_tag = container.select_one(get_article_contents_selectors.get("tags").get("tag"))  # 如果不是 <a> 標籤，則查找子元素 <a>
      if c_tag:
        c_tag_text = c_tag.get_text(strip=True)
        print(f"找到Tag: {c_tag_text}")

c_author = article_content_container[0].select_one(get_article_contents_selectors.get("author"))
c_a_text = c_author.get_text(strip=True) if c_author else None
print(f'author: {c_a_text}')

c_content_container = article_content_container[0].select_one(get_article_contents_selectors.get("content"))
if c_content_container:
    all_text = []
    for element in c_content_container.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol']):
        text = element.get_text(strip=True)
        if text:
            all_text.append(text)
    full_content = "\n".join(all_text)
    print(full_content)
else:
    print("找不到文章內容容器")




