import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from src.crawlers.bnext_content_extractor import BnextContentExtractor
from src.crawlers.configs.site_config import SiteConfig

@pytest.fixture
def mock_config():
    """建立模擬的網站配置"""
    config = Mock(spec=SiteConfig)
    config.name = "bnext"
    config.base_url = "https://www.bnext.com.tw"
    # 根據 bnext_crawler_config.json 設定正確的選擇器
    config.selectors = {
        'get_article_contents': {
            'content_container': "body > div.main-body-content > div > div.article-lw.pb-4.lg\\:py-4",
            'published_date': "#hero > div.rgt.md\\:my-6.lg\\:mr-6 > div.pc.h-full.hidden.lg\\:flex.flex-col.gap-2.tracking-wide.leading-normal > div.flex.gap-1.items-center.text-sm.text-gray-800 > span:nth-child(1)",
            'category': "#hero > div.rgt.md\\:my-6.lg\\:mr-6 > div.pc.h-full.hidden.lg\\:flex.flex-col.gap-2.tracking-wide.leading-normal > div.flex.gap-1.items-center.text-sm.text-gray-800 > a",
            'title': "#hero > div.rgt.md\\:my-6.lg\\:mr-6 > div.pc.h-full.hidden.lg\\:flex.flex-col.gap-2.tracking-wide.leading-normal > h1",
            'summary': "#hero > div.rgt.md\\:my-6.lg\\:mr-6 > div.pc.h-full.hidden.lg\\:flex.flex-col.gap-2.tracking-wide.leading-normal > div:nth-child(3)",
            'tags': {
                'container': "#hero > div.rgt.md\\:my-6.lg\\:mr-6 > div.pc.h-full.hidden.lg\\:flex.flex-col.gap-2.tracking-wide.leading-normal > div.flex.gap-1.flex-wrap",
                'tag': "a"
            },
            'author': "#hero > div.rgt.md\\:my-6.lg\\:mr-6 > div.pc.h-full.hidden.lg\\:flex.flex-col.gap-2.tracking-wide.leading-normal > div.flex.gap-2.items-center.text-sm.text-gray-800 > a",
            'content': "#article > div > div.left > div > div.center.flex.flex-col.gap-4 > div.htmlview.article-content"
        }
    }
    
    # 添加其他必要的配置項
    config.categories = ["ai", "tech", "iot", "smartmedical", "smartcity"]
    config.full_categories = ["ai", "tech", "iot", "smartmedical", "smartcity", 
                              "cloudcomputing", "security", "articles", "5g", 
                              "car", "blockchain", "energy", "semiconductor", "manufacture"]
    config.article_settings = {
        "max_pages": 3,
        "ai_only": True,
        "num_articles": 10,
        "min_keywords": 3
    }
    config.extraction_settings = {
        "num_articles": 3,
        "min_keywords": 3
    }
    config.storage_settings = {
        "save_to_csv": True,
        "save_to_database": False
    }
    config.valid_domains = ["https://www.bnext.com.tw"]
    config.url_patterns = ["/categories/", "/articles/"]
    config.url_file_extensions = [".html", ""]
    config.date_format = "%Y-%m-%d"
    config.list_url_template = "{base_url}/categories/{category}"
    
    # 模擬方法
    config.get_category_url = Mock(return_value="https://www.bnext.com.tw/categories/ai")
    config.validate = Mock(return_value=True)
    config.validate_url = Mock(return_value=True)
    
    return config

@pytest.fixture
def example_html():
    """提供測試用的文章HTML"""
    return """
    <body>
        <div class="main-body-content">
            <div>
                <div class="article-lw pb-4 lg:py-4">
                    <section id="hero">
                        <div class="rgt md:my-6 lg:mr-6">
                            <div class="pc h-full hidden lg:flex flex-col gap-2 tracking-wide leading-normal">
                                <div class="flex gap-1 items-center text-sm text-gray-800">
                                    <span>2025.04.04</span>
                                    <span>|</span>
                                    <a class="text-primary" href="https://www.bnext.com.tw/categories/ai">AI與大數據</a>
                                </div>
                                <h1 class="text-4xl font-semibold">DeepL讓開會沒有「老外」！德鐵、日經都在用的AI快譯通，記者會即時上字也難不倒</h1>
                                <div class="text-sm text-gray-800">API大降價，人人都是AI玩家。應用領域中，來自德國、專攻翻譯的DeepL，要拿什麼與大型語言模型和Google翻譯競爭？</div>
                                <div class="flex gap-1 flex-wrap">
                                    <a class="inline-block px-1 text-primary text-sm hover:bg-primary/10" href="https://www.bnext.com.tw/tags/Google">＃Google</a>
                                    <a class="inline-block px-1 text-primary text-sm hover:bg-primary/10" href="https://www.bnext.com.tw/tags/%E4%BA%BA%E5%B7%A5%E6%99%BA%E6%85%A7">＃人工智慧</a>
                                    <a class="inline-block px-1 text-primary text-sm hover:bg-primary/10" href="https://www.bnext.com.tw/tags/AI">＃AI</a>
                                </div>
                                <div class="flex gap-2 items-center text-sm text-gray-800">
                                    <a class="flex gap-2 items-center" href="https://www.bnext.com.tw/author/4900">
                                        <img class="rounded-full w-6 h-6" src="https://image-cdn.learnin.tw/bnextmedia/image/people/2016-09/img-1473057973-60272.png">
                                        <span>吳玲臻</span>
                                    </a>
                                    <a class="flex gap-2 items-center" href="https://www.bnext.com.tw/author/2860">
                                        <img class="rounded-full w-6 h-6" src="https://image-cdn.learnin.tw/bnextmedia/image/people/2016-09/img-1473057973-60272.png">
                                        <span>陳君毅</span>
                                    </a>
                                </div>
                            </div>
                        </div>
                    </section>
                    <div id="article">
                        <div>
                            <div class="left">
                                <div>
                                    <div class="center flex flex-col gap-4">
                                        <div class="htmlview article-content">
                                            <p>盤點，是一種對未來想像的策展。遍布全球的AI 100、立足台灣的AI 50當中，可以拼湊出關鍵趨勢。從這一次封面故事的報導和專訪中，我們試圖勾勒出AI產業的當下與未來。</p>
                                            <h2>語言巴別塔 —— DeepL</h2>
                                            <p>就算AI應用五花八門，卻幾乎沒有聽到誰在做「翻譯」。這個領域似乎被大型語言模型（LLM）「順手」解決了——有看不懂的外文文章，就通篇交給ChatGPT，不然也能在Google翻譯手工查詢。</p>
                                            <p>翻譯領域的新進者，要不是跟大型語言模型競爭，就是要直接對抗Google翻譯，2個對手的共通之處就是背後擁有近乎無限的資源。</p>
                                            <p>2017年創立、提供AI翻譯工具的德國新創公司DeepL，就是有膽發起競爭的勇者。</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    """

@pytest.fixture
def extractor(mock_config):
    """建立 BnextContentExtractor 實例"""
    return BnextContentExtractor(config=mock_config)

def test_init_with_no_config():
    """測試初始化時沒有提供配置"""
    with pytest.raises(ValueError, match="未提供網站配置，請提供有效的配置"):
        BnextContentExtractor()

def test_init_with_config(extractor, mock_config):
    """測試初始化時提供配置"""
    assert extractor.site_config == mock_config

def test_update_config_with_no_config(extractor):
    """測試更新配置時沒有提供配置"""
    with pytest.raises(ValueError, match="未提供網站配置，請提供有效的配置"):
        extractor.update_config()

def test_update_config_with_config(extractor):
    """測試更新配置"""
    new_config = Mock(spec=SiteConfig)
    extractor.update_config(new_config)
    assert extractor.site_config == new_config

@patch('requests.get')
@patch('src.crawlers.bnext_utils.BnextUtils.get_soup_from_html')
@patch('src.crawlers.bnext_utils.BnextUtils.sleep_random_time')
@patch('src.crawlers.bnext_utils.BnextUtils.get_article_columns_dict')
@patch('src.crawlers.article_analyzer.ArticleAnalyzer.is_ai_related')
def test_get_article_content_success(mock_is_ai_related, mock_get_article_columns, mock_sleep, mock_get_soup, mock_get, extractor, example_html):
    """測試成功獲取文章內容"""
    # 設置模擬的回應
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = example_html
    mock_get.return_value = mock_response
    
    # 設置模擬的 BnextUtils 方法
    mock_get_soup.return_value = BeautifulSoup(example_html, 'html.parser')
    
    # 設置 is_ai_related 返回值
    mock_is_ai_related.return_value = True
    
    # 設置 get_article_columns_dict 返回值
    expected_result = {
        'title': 'DeepL讓開會沒有「老外」！德鐵、日經都在用的AI快譯通，記者會即時上字也難不倒',
        'summary': 'API大降價，人人都是AI玩家。應用領域中，來自德國、專攻翻譯的DeepL，要拿什麼與大型語言模型和Google翻譯競爭？',
        'content': '盤點，是一種對未來想像的策展。遍布全球的AI 100、立足台灣的AI 50當中，可以拼湊出關鍵趨勢。從這一次封面故事的報導和專訪中，我們試圖勾勒出AI產業的當下與未來。',
        'link': 'https://www.bnext.com.tw/article/82812/deepl-ai100',
        'category': 'AI與大數據',
        'published_at': '2025.04.04',
        'author': '吳玲臻',
        'source': 'bnext',
        'source_url': 'https://www.bnext.com.tw',
        'article_type': None,
        'tags': 'Google,人工智慧,AI',
        'is_ai_related': True,
        'is_scraped': True,
        'scrape_status': 'content_scraped',
        'scrape_error': None,
        'last_scrape_attempt': datetime.now(timezone.utc),
        'task_id': None
    }
    mock_get_article_columns.return_value = expected_result
    
    # 測試 _get_article_content 方法
    result = extractor._get_article_content(
        'https://www.bnext.com.tw/article/82812/deepl-ai100',
        ai_only=True,
        min_keywords=3
    )
    
    # 只驗證結果
    assert result is not None
    assert result['title'] == 'DeepL讓開會沒有「老外」！德鐵、日經都在用的AI快譯通，記者會即時上字也難不倒'
    assert result['category'] == 'AI與大數據'
    assert result['tags'] == 'Google,人工智慧,AI'
    assert result['is_ai_related'] == True
    assert result['scrape_status'] == 'content_scraped'
    assert result['scrape_error'] is None
    assert result['last_scrape_attempt'] is not None

@patch('requests.get')
def test_get_article_content_request_failed(mock_get, extractor):
    """測試獲取文章內容請求失敗"""
    # 設置模擬的失敗回應
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    
    # 測試 _get_article_content 方法
    result = extractor._get_article_content(
        'https://www.bnext.com.tw/article/invalid',
        ai_only=True,
        min_keywords=3
    )
    
    # 驗證結果
    assert result is None

@patch('requests.get')
@patch('src.crawlers.bnext_utils.BnextUtils.get_soup_from_html')
@patch('src.crawlers.bnext_utils.BnextUtils.get_article_columns_dict')
@patch('src.crawlers.article_analyzer.ArticleAnalyzer.is_ai_related')
def test_get_article_content_not_ai_related(mock_is_ai_related, mock_get_article_columns, mock_get_soup, mock_get, extractor, example_html):
    """測試獲取非AI相關文章內容"""
    # 設置模擬的回應
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = example_html
    mock_get.return_value = mock_response
    
    # 設置模擬的 BnextUtils 方法
    mock_get_soup.return_value = BeautifulSoup(example_html, 'html.parser')
    
    # 設置 is_ai_related 返回值
    mock_is_ai_related.return_value = False
    
    # 設置初始 get_article_columns_dict 返回值
    mock_article_data = {
        'title': '非AI相關文章標題',
        'summary': '這是一篇非AI相關的文章摘要',
        'content': '這是一篇非AI相關的文章內容',
        'link': 'https://www.bnext.com.tw/article/12345/non-ai',
        'category': '金融科技',
        'published_at': '2025.04.04',
        'author': '測試作者',
        'source': 'bnext',
        'source_url': 'https://www.bnext.com.tw',
        'article_type': None,
        'tags': '金融,區塊鏈',
        'is_ai_related': False,
        'is_scraped': True,
        'scrape_status': 'content_scraped',
        'scrape_error': "文章不符合 AI 相關條件",
        'last_scrape_attempt': datetime.now(timezone.utc),
        'task_id': None
    }
    
    mock_get_article_columns.return_value = mock_article_data
    
    # 測試 _get_article_content 方法
    result = extractor._get_article_content(
        'https://www.bnext.com.tw/article/12345/non-ai',
        ai_only=True,
        min_keywords=3
    )
    
    # 驗證結果
    assert result is not None
    assert result['scrape_status'] == 'content_scraped'
    assert result['scrape_error'] == "文章不符合 AI 相關條件"
    assert result['is_ai_related'] == False
    assert result['last_scrape_attempt'] is not None

@patch('src.crawlers.bnext_content_extractor.BnextContentExtractor._get_article_content')
def test_batch_get_articles_content_with_new_fields(mock_get_content, extractor):
    """測試批量獲取文章內容同時處理新欄位"""
    # 創建測試用的 DataFrame
    test_df = pd.DataFrame({
        'title': ['文章1', '文章2', '文章3'],
        'link': ['http://example.com/1', 'http://example.com/2', 'http://example.com/3'],
        'is_ai_related': [False, False, False],
        'is_scraped': [False, False, False],
        'scrape_status': ['pending', 'pending', 'pending'],
        'scrape_error': [None, None, None],
        'last_scrape_attempt': [None, None, None],
        'task_id': [None, None, None]
    })
    
    # 設置模擬的返回值
    article1 = {
        'title': '文章1',
        'link': 'http://example.com/1',
        'is_ai_related': True,
        'is_scraped': True,
        'scrape_status': 'content_scraped',
        'scrape_error': None,
        'last_scrape_attempt': datetime.now(timezone.utc),
        'task_id': 123
    }
    article2 = {
        'title': '文章2',
        'link': 'http://example.com/2',
        'is_ai_related': False,
        'is_scraped': True,
        'scrape_status': 'content_scraped',
        'scrape_error': '文章不符合 AI 相關條件',
        'last_scrape_attempt': datetime.now(timezone.utc),
        'task_id': 123
    }
    article3 = None  # 模擬失敗
    
    mock_get_content.side_effect = [article1, article2, article3]
    
    # 調用測試方法
    result = extractor.batch_get_articles_content(test_df, num_articles=3, ai_only=True, min_keywords=3)
    
    # 驗證結果
    assert len(result) == 3  # 包含失敗的文章
    assert result[0]['scrape_status'] == 'content_scraped'
    assert result[1]['scrape_status'] == 'content_scraped'
    assert result[2]['scrape_status'] == 'failed'  # 失敗的文章應該有 failed 狀態

@patch('src.crawlers.bnext_utils.BnextUtils.get_article_columns_dict')
def test_extract_article_parts(mock_get_article_columns, extractor, example_html):
    """測試提取文章各部分"""
    # 創建 BeautifulSoup 對象
    soup = BeautifulSoup(example_html, 'html.parser')
    article_container = soup.select('div.article-lw.pb-4.lg\\:py-4')
    
    # 設置 get_article_columns_dict 的返回值
    expected_result = {
        'title': 'DeepL讓開會沒有「老外」！德鐵、日經都在用的AI快譯通，記者會即時上字也難不倒',
        'summary': 'API大降價，人人都是AI玩家。應用領域中，來自德國、專攻翻譯的DeepL，要拿什麼與大型語言模型和Google翻譯競爭？',
        'content': '盤點，是一種對未來想像的策展。遍布全球的AI 100、立足台灣的AI 50當中，可以拼湊出關鍵趨勢。從這一次封面故事的報導和專訪中，我們試圖勾勒出AI產業的當下與未來。',
        'link': 'https://test.com/article',
        'category': 'AI與大數據',
        'published_at': '2025.04.04',
        'author': '吳玲臻,陳君毅',
        'source': 'bnext',
        'source_url': 'https://www.bnext.com.tw',
        'article_type': None,
        'tags': 'Google,人工智慧,AI',
        'is_ai_related': True,
        'is_scraped': True
    }
    mock_get_article_columns.return_value = expected_result
    
    # 執行測試
    result = extractor._extract_article_parts(
        article_container,
        soup,
        extractor.site_config.selectors['get_article_contents'],
        'https://test.com/article',
        ai_only=True
    )
    
    # 驗證結果
    assert result == expected_result

def test_extract_article_parts_no_container(extractor):
    """測試提取文章各部分時沒有容器"""
    result = extractor._extract_article_parts(
        [],
        BeautifulSoup('', 'html.parser'),
        extractor.site_config.selectors['get_article_contents'],
        'https://test.com/article',
        ai_only=True
    )
    
    # 驗證結果
    assert result is None
