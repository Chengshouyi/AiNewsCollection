from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class SiteConfig:
    """網站配置類別"""
    name: str
    base_url: str
    list_url_template: str
    selectors: Dict[str, List[Dict]] = field(default_factory=dict)
    valid_domains: List[str] = field(default_factory=list)
    url_patterns: List[str] = field(default_factory=list)
    url_file_extensions: List[str] = field(default_factory=lambda: ['.html', '.htm'])
    date_format: str = '%Y/%m/%d %H:%M'
    
    # 選擇器配置
    selectors: Dict[str, List[Dict]] = field(default_factory=dict)
    
 def __post_init__(self):
    default_selectors = {'list': [], 'content': [], 'date': [], 'title': [], 'pagination': []}
    self.selectors = {**default_selectors, **self.selectors}
    if not self.valid_domains: self.valid_domains = [self.base_url]
    
def validate_url(self, url: str) -> bool:
    if not url or not any(url.startswith(domain) for domain in self.valid_domains):
            return False
    if not any(pattern in url for pattern in self.url_patterns):
        return False
    if self.url_file_extensions and not any(url.endswith(ext) for ext in self.url_file_extensions):
        return False
    return True
    
def __post_init__(self):
    # 確保選擇器配置包含所有必要的鍵
    default_selectors = {
         'list': [],
         'content': [],
         'date': [],
         'title': [],
         'pagination': []
        }
    self.selectors = {**default_selectors, **self.selectors}
        
    # 設置默認的有效域名
    if not self.valid_domains:
        self.valid_domains = [self.base_url]
    
def validate_url(self, url: str) -> bool:
    """驗證 URL 是否符合網站格式"""
    if not url:
        return False
        
    # 檢查基本 URL
    if not any(url.startswith(domain) for domain in self.valid_domains):
        return False
        
    # 檢查 URL 格式
    if not any(pattern in url for pattern in self.url_patterns):
        return False
        
    # 檢查文件擴展名（如果有設置）
    if self.url_file_extensions and not any(url.endswith(ext) for ext in self.url_file_extensions):
        return False
            
    return True

# 网易科技配置
TECH163_CONFIG = SiteConfig(
    name='tech163',
    base_url='https://tech.163.com/',
    list_url_template='{base_url}',
    valid_domains=['https://tech.163.com', 'https://www.163.com'],
    url_patterns=['/tech/', '/dy/article/', '/special/', '/[0-9]{8}/'],
    url_file_extensions=['.html', '.htm', ''],
    date_format='%Y-%m-%d %H:%M',  # 根據實際日期格式調整
    selectors={
        'list': [
            # 最新快訊區域
            {'tag': 'div', 'attrs': {'class': 'hot-list'}},  # 主新聞列表容器
            {'tag': 'div', 'attrs': {'class': 'hot_board'}},  # 單條新聞容器
            {'tag': 'div', 'attrs': {'class': 'hb_detail'}},  # 新聞詳情容器
            {'tag': 'a', 'attrs': {}},  # 新聞連結與標題
            # 右側欄 - 智能
            {'tag': 'div', 'attrs': {'class': 'bc_detail'}},  # 智能新聞容器
            # 右側欄 - 後廠村7號
            {'tag': 'div', 'attrs': {'class': 'smart_detail'}},  # 後廠村7號容器
        ],
        'content': [
            {'tag': 'div', 'attrs': {'class': 'post_text'}},  # 正文主要容器
            {'tag': 'div', 'attrs': {'class': 'article-body'}},  # 備用正文容器
        ],
        'date': [
            {'tag': 'span', 'attrs': {'class': 'time'}},  # 發佈時間
            {'tag': 'time', 'attrs': {}},  # 備用時間標籤
        ],
        'title': [
            {'tag': 'h1', 'attrs': {'class': 'post_title'}},  # 詳細頁標題
            {'tag': 'h1', 'attrs': {'class': 'article-title'}},  # 備用標題
        ],
        'pagination': [
            {'tag': 'a', 'attrs': {'class': 'load_more_btn'}},  # 加載更多按鈕
        ]
    }
)