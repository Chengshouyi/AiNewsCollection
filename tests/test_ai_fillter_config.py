"""測試 AI 過濾器配置 (ai_filter_config) 的相關功能。"""

# test_ai_config.py
from src.crawlers.configs.ai_filter_config import AI_KEYWORDS, AI_CATEGORIES, HIGH_PRIORITY_KEYWORDS, register_additional_keywords, register_additional_categories
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger

logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger

def test_ai_keywords_is_set():
    """測試 AI_KEYWORDS 是否為 set 類型"""
    assert isinstance(AI_KEYWORDS, set)
    assert len(AI_KEYWORDS) > 0  # 確保集合不為空

def test_ai_categories_is_set():
    """測試 AI_CATEGORIES 是否為 set 類型"""
    assert isinstance(AI_CATEGORIES, set)
    assert len(AI_CATEGORIES) > 0  # 確保集合不為空

def test_high_priority_keywords_is_set():
    """測試 HIGH_PRIORITY_KEYWORDS 是否為 set 類型"""
    assert isinstance(HIGH_PRIORITY_KEYWORDS, set)
    assert len(HIGH_PRIORITY_KEYWORDS) > 0  # 確保集合不為空

def test_register_additional_keywords():
    """測試 register_additional_keywords 函數是否能正確註冊新的關鍵字"""
    initial_keyword_count = len(AI_KEYWORDS)
    new_keywords = ["new_ai", "新人工智慧"]
    register_additional_keywords(*new_keywords)
    for keyword in new_keywords:
        assert keyword.lower() in AI_KEYWORDS
    assert len(AI_KEYWORDS) == initial_keyword_count + len(new_keywords)

    # 清理新增的關鍵字，避免影響其他測試 (可選)
    for keyword in new_keywords:
        AI_KEYWORDS.discard(keyword.lower())

def test_register_additional_categories():
    """測試 register_additional_categories 函數是否能正確註冊新的分類"""
    initial_category_count = len(AI_CATEGORIES)
    new_categories = ["novel ai field", "新ai領域"]
    register_additional_categories(*new_categories)
    for category in new_categories:
        assert category.lower() in AI_CATEGORIES
    assert len(AI_CATEGORIES) == initial_category_count + len(new_categories)

    # 清理新增的分類，避免影響其他測試 (可選)
    for category in new_categories:
        AI_CATEGORIES.discard(category.lower())

def test_keywords_are_lowercase():
    """測試 AI_KEYWORDS 中的所有關鍵字是否都是小寫"""
    for keyword in AI_KEYWORDS:
        assert keyword.lower() == keyword

def test_categories_are_lowercase():
    """測試 AI_CATEGORIES 中的所有分類是否都是小寫"""
    for category in AI_CATEGORIES:
        assert category.lower() == category

def test_high_priority_keywords_are_lowercase():
    """測試 HIGH_PRIORITY_KEYWORDS 中的所有關鍵字是否都是小寫"""
    for keyword in HIGH_PRIORITY_KEYWORDS:
        assert keyword.lower() == keyword