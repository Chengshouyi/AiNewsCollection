from src.crawler.site_config import SiteConfig

# 數位時代網站配置
BNEXT_CONFIG = SiteConfig(
    name='bnext',
    base_url='https://www.bnext.com.tw',
    list_url_template='{base_url}/categories/{category}',
    valid_domains=['https://www.bnext.com.tw'],
    url_patterns=['/categories/', '/articles/'],
    url_file_extensions=['.html', ''],
    date_format='%Y-%m-%d',
    selectors={
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
            {'tag': 'div', 'attrs': {'class': 'author'}},
            {'tag': 'span', 'attrs': {'class': 'writer'}},
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

# 預設類別URL列表
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

