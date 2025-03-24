from src.crawlers.site_config import SiteConfig
import json
import os
from src.config import BNEXT_CONFIG_PATH

def load_config_file(config_file_path):
    """從JSON檔案載入配置"""
    try:
        with open(config_file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"無法載入配置檔案：{e}")
        return None

# 配置檔案的路徑
config_file_path = BNEXT_CONFIG_PATH

# 確保配置目錄存在
os.makedirs(os.path.dirname(config_file_path), exist_ok=True)

# 如果配置檔案不存在，則建立它
if not os.path.exists(config_file_path):
    default_config = {
        "name": "bnext",
        "base_url": "https://www.bnext.com.tw",
        "list_url_template": "{base_url}/categories/{category}",
        "valid_domains": ["https://www.bnext.com.tw"],
        "url_patterns": ["/categories/", "/articles/"],
        "url_file_extensions": [".html", ""],
        "date_format": "%Y-%m-%d",
        "selectors": {
            # 文章列表頁選擇器
            'focus_articles': [
                {'tag': 'div', 'attrs': {'class': 'grid grid-cols-6 gap-4 relative h-full'}, 'parent': {'class': 'pc hidden lg:block'}},
                {'tag': 'h2', 'attrs': {}, 'parent': {'class': 'col-span-3 flex flex-col flex-grow gap-y-3 m-4'}},
                {'tag': 'div', 'attrs': {'class': 'flex-grow pt-4 text-lg text-gray-500'}, 'parent': {'class': 'col-span-3 flex flex-col flex-grow gap-y-3 m-4'}},
                {'tag': 'a', 'attrs': {}, 'parent': {'class': 'flex relative items-center gap-2 text-gray-500 text-sm'}},
                {'tag': 'span', 'attrs': {}, 'parent': {'class': 'flex relative items-center gap-2 text-gray-500 text-sm'}, 'nth_child': 3}
            ],
            'regular_articles': [
                {'tag': 'div', 'attrs': {'class': 'grid grid-cols-4 gap-8 xl:gap-6'}, 'parent': {'class': 'pc hidden lg:block'}},
                {'tag': 'h2', 'attrs': {}, 'parent': {'class': 'flex flex-col'}},
                {'tag': 'div', 'attrs': {'class': 'text-sm text-justify font-normal text-gray-500 three-line-text tracking-wide'}},
                {'tag': 'a', 'attrs': {}, 'parent': {'class': 'flex relative items-center gap-2 text-xs text-gray-500 font-normal'}},
                {'tag': 'span', 'attrs': {}, 'parent': {'class': 'flex relative items-center gap-2 text-xs text-gray-500 font-normal'}, 'nth_child': 3}
            ],
            
            # 文章詳細頁選擇器
            'article_detail': [
                {'tag': 'div', 'attrs': {'class': 'pc h-full hidden lg:flex flex-col gap-2 tracking-wide leading-normal'}, 'parent': {'id': 'hero'}, 'purpose': 'header'},
                {'tag': 'span', 'attrs': {}, 'parent': {'class': 'flex gap-1 items-center text-sm text-gray-800'}, 'nth_child': 1, 'purpose': 'publish_date'},
                {'tag': 'a', 'attrs': {}, 'parent': {'class': 'flex gap-1 items-center text-sm text-gray-800'}, 'purpose': 'category'},
                {'tag': 'h1', 'attrs': {}, 'purpose': 'title'},
                {'tag': 'div', 'attrs': {}, 'nth_child': 3, 'purpose': 'summary'},
                {'tag': 'div', 'attrs': {'class': 'flex gap-1 flex-wrap'}, 'purpose': 'tags_container'},
                {'tag': 'a', 'attrs': {}, 'purpose': 'tag'},
                {'tag': 'a', 'attrs': {}, 'parent': {'class': 'flex gap-2 items-center text-sm text-gray-800'}, 'purpose': 'author'},
                {'tag': 'div', 'attrs': {'class': 'htmlview article-content'}, 'purpose': 'content'},
                {'tag': 'p', 'attrs': {}, 'purpose': 'content_paragraph'},
                {'tag': 'h2', 'attrs': {}, 'purpose': 'content_heading'},
                {'tag': 'a', 'attrs': {}, 'parent': {'tag': 'blockquote'}, 'purpose': 'related_links'}
            ],
            'common_elements': [
                {'tag': 'time', 'attrs': {}},
                {'tag': 'div', 'attrs': {'class': 'author'}},
                {'tag': 'div', 'attrs': {'class': 'read-count'}},
                {'tag': 'a', 'attrs': {'href': '/article/'}}
            ],
            'backup_articles': [
                {'tag': 'div', 'attrs': {'class': 'article-card'}},
                {'tag': 'div', 'attrs': {'class': 'article-item'}},
                {'tag': 'div', 'attrs': {'class': 'article-list-item'}},
                {'tag': 'a', 'attrs': {'href': '/article/'}}
            ],
            'list': [
                {'tag': 'div', 'attrs': {'class': 'article-list'}},
                {'tag': 'a', 'attrs': {'class': 'article-link'}},
            ],
            'content': [
                {'tag': 'article', 'attrs': {'class': 'post-content'}},
                {'tag': 'div', 'attrs': {'class': 'article-content'}},
                {'tag': 'div', 'attrs': {'class': 'article-body'}},
                {'tag': 'div', 'attrs': {'id': 'article-content'}},
                {'tag': 'div', 'attrs': {'class': 'post-content'}},
            ],
            'date': [
                {'tag': 'time', 'attrs': {'class': 'published-date'}},
                {'tag': 'span', 'attrs': {'class': 'date'}},
                {'tag': 'time', 'attrs': {}},
            ],
            'title': [
                {'tag': 'h1', 'attrs': {'class': 'article-title'}},
                {'tag': 'h1', 'attrs': {'class': 'post-title'}},
            ],
            'author': [
                {'tag': 'div', 'attrs': {'class': 'article-author'}},
            ],
            'tags': [
                {'tag': 'div', 'attrs': {'class': 'tags'}},
                {'tag': 'div', 'attrs': {'class': 'article-tags'}},
                {'tag': 'a', 'attrs': {'class': 'tag'}},
            ],
            'related_articles': [
                {'tag': 'div', 'attrs': {'class': 'related-article'}},
                {'tag': 'div', 'attrs': {'class': 'related-post'}},
                {'tag': 'div', 'attrs': {'class': 'more-article'}},
            ],
            'pagination': [
                {'tag': 'a', 'attrs': {'class': 'next-page'}},
            ]
        },
        "default_categories": [
            "ai",
            "tech",
            "iot",
            "smartmedical",
            "smartcity",
            "cloudcomputing",
            "security",
            "articles",
            "5g",
            "car",
            "blockchain",
            "energy",
            "semiconductor",
            "manufacture"
        ]
    }
    try:
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        print(f"已建立預設配置檔案：{config_file_path}")
    except Exception as e:
        print(f"無法建立配置檔案：{e}")

# 載入配置
config_data = load_config_file(config_file_path)

if config_data:
    # 從JSON配置建立SiteConfig物件
    BNEXT_CONFIG = SiteConfig(
        name=config_data['name'],
        base_url=config_data['base_url'],
        list_url_template=config_data['list_url_template'],
        valid_domains=config_data['valid_domains'],
        url_patterns=config_data['url_patterns'],
        url_file_extensions=config_data['url_file_extensions'],
        date_format=config_data['date_format'],
        selectors=config_data['selectors']
    )
    
    # 載入預設類別URL列表
    BNEXT_DEFAULT_CATEGORIES = config_data['default_categories']
else:
    # 如果無法載入配置，使用原始的硬編碼配置
    print("使用預設硬編碼配置")
    BNEXT_CONFIG = SiteConfig(
        name='bnext',
        base_url='https://www.bnext.com.tw',
        list_url_template='{base_url}/categories/{category}',
        valid_domains=['https://www.bnext.com.tw'],
        url_patterns=['/categories/', '/articles/'],
        url_file_extensions=['.html', ''],
        date_format='%Y-%m-%d',
        selectors={
             # 文章列表頁選擇器
            'focus_articles': [
                {'tag': 'div', 'attrs': {'class': 'grid grid-cols-6 gap-4 relative h-full'}, 'parent': {'class': 'pc hidden lg:block'}},
                {'tag': 'h2', 'attrs': {}, 'parent': {'class': 'col-span-3 flex flex-col flex-grow gap-y-3 m-4'}},
                {'tag': 'div', 'attrs': {'class': 'flex-grow pt-4 text-lg text-gray-500'}, 'parent': {'class': 'col-span-3 flex flex-col flex-grow gap-y-3 m-4'}},
                {'tag': 'a', 'attrs': {}, 'parent': {'class': 'flex relative items-center gap-2 text-gray-500 text-sm'}},
                {'tag': 'span', 'attrs': {}, 'parent': {'class': 'flex relative items-center gap-2 text-gray-500 text-sm'}, 'nth_child': 3}
            ],
            'regular_articles': [
                {'tag': 'div', 'attrs': {'class': 'grid grid-cols-4 gap-8 xl:gap-6'}, 'parent': {'class': 'pc hidden lg:block'}},
                {'tag': 'h2', 'attrs': {}, 'parent': {'class': 'flex flex-col'}},
                {'tag': 'div', 'attrs': {'class': 'text-sm text-justify font-normal text-gray-500 three-line-text tracking-wide'}},
                {'tag': 'a', 'attrs': {}, 'parent': {'class': 'flex relative items-center gap-2 text-xs text-gray-500 font-normal'}},
                {'tag': 'span', 'attrs': {}, 'parent': {'class': 'flex relative items-center gap-2 text-xs text-gray-500 font-normal'}, 'nth_child': 3}
            ],
            
            # 文章詳細頁選擇器
            'article_detail': [
                {'tag': 'div', 'attrs': {'class': 'pc h-full hidden lg:flex flex-col gap-2 tracking-wide leading-normal'}, 'parent': {'id': 'hero'}, 'purpose': 'header'},
                {'tag': 'span', 'attrs': {}, 'parent': {'class': 'flex gap-1 items-center text-sm text-gray-800'}, 'nth_child': 1, 'purpose': 'publish_date'},
                {'tag': 'a', 'attrs': {}, 'parent': {'class': 'flex gap-1 items-center text-sm text-gray-800'}, 'purpose': 'category'},
                {'tag': 'h1', 'attrs': {}, 'purpose': 'title'},
                {'tag': 'div', 'attrs': {}, 'nth_child': 3, 'purpose': 'summary'},
                {'tag': 'div', 'attrs': {'class': 'flex gap-1 flex-wrap'}, 'purpose': 'tags_container'},
                {'tag': 'a', 'attrs': {}, 'purpose': 'tag'},
                {'tag': 'a', 'attrs': {}, 'parent': {'class': 'flex gap-2 items-center text-sm text-gray-800'}, 'purpose': 'author'},
                {'tag': 'div', 'attrs': {'class': 'htmlview article-content'}, 'purpose': 'content'},
                {'tag': 'p', 'attrs': {}, 'purpose': 'content_paragraph'},
                {'tag': 'h2', 'attrs': {}, 'purpose': 'content_heading'},
                {'tag': 'a', 'attrs': {}, 'parent': {'tag': 'blockquote'}, 'purpose': 'related_links'}
            ],
            'common_elements': [
                {'tag': 'time', 'attrs': {}},
                {'tag': 'div', 'attrs': {'class': 'author'}},
                {'tag': 'div', 'attrs': {'class': 'read-count'}},
                {'tag': 'a', 'attrs': {'href': '/article/'}}
            ],
            'backup_articles': [
                {'tag': 'div', 'attrs': {'class': 'article-card'}},
                {'tag': 'div', 'attrs': {'class': 'article-item'}},
                {'tag': 'div', 'attrs': {'class': 'article-list-item'}},
                {'tag': 'a', 'attrs': {'href': '/article/'}}
            ],
            'list': [
                {'tag': 'div', 'attrs': {'class': 'article-list'}},
                {'tag': 'a', 'attrs': {'class': 'article-link'}},
            ],
            'content': [
                {'tag': 'article', 'attrs': {'class': 'post-content'}},
                {'tag': 'div', 'attrs': {'class': 'article-content'}},
                {'tag': 'div', 'attrs': {'class': 'article-body'}},
                {'tag': 'div', 'attrs': {'id': 'article-content'}},
                {'tag': 'div', 'attrs': {'class': 'post-content'}},
            ],
            'date': [
                {'tag': 'time', 'attrs': {'class': 'published-date'}},
                {'tag': 'span', 'attrs': {'class': 'date'}},
                {'tag': 'time', 'attrs': {}},
            ],
            'title': [
                {'tag': 'h1', 'attrs': {'class': 'article-title'}},
                {'tag': 'h1', 'attrs': {'class': 'post-title'}},
            ],
            'author': [
                {'tag': 'div', 'attrs': {'class': 'article-author'}},
            ],
            'tags': [
                {'tag': 'div', 'attrs': {'class': 'tags'}},
                {'tag': 'div', 'attrs': {'class': 'article-tags'}},
                {'tag': 'a', 'attrs': {'class': 'tag'}},
            ],
            'related_articles': [
                {'tag': 'div', 'attrs': {'class': 'related-article'}},
                {'tag': 'div', 'attrs': {'class': 'related-post'}},
                {'tag': 'div', 'attrs': {'class': 'more-article'}},
            ],
            'pagination': [
                {'tag': 'a', 'attrs': {'class': 'next-page'}},
            ]
        }
    )
    
    BNEXT_DEFAULT_CATEGORIES = [
        'ai',           # AI與大數據
        'tech',         # 科技總覽
        'iot',          # 物聯網
        'smartmedical', # 醫療生技
        'smartcity',    # 智慧城市
        'cloudcomputing', # 雲端運算與服務
        'security',     # 資訊安全
        'articles',     # 最新新聞
        '5g',           # 5G通訊
        'car',          # 電動車／交通科技
        'blockchain',   # 區塊鏈
        'energy',       # 能源環保
        'semiconductor', # 半導體與電子產業
        'manufacture',  # 智慧製造
    ]

