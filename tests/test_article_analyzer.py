"""測試 ArticleAnalyzer 類別的功能。"""

import pandas as pd
import pytest

from src.crawlers.article_analyzer import ArticleAnalyzer
from src.crawlers.configs.ai_filter_config import AI_KEYWORDS
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger


class TestArticleAnalyzer:
    def test_is_ai_related_by_category(self):
        """測試文章分類為AI相關時，is_ai_related 應返回 True"""
        article = {"category": "Artificial Intelligence"}
        assert ArticleAnalyzer.is_ai_related(article) is True

    def test_is_ai_related_by_title_keyword(self):
        """測試文章標題包含AI關鍵字時，is_ai_related 應返回 True"""
        article = {"title": "深度學習在醫療領域的應用"}
        assert ArticleAnalyzer.is_ai_related(article) is True

    def test_is_ai_related_by_tags_keyword_string(self):
        """測試文章標籤（字串）包含AI關鍵字時，is_ai_related 應返回 True"""
        article = {"tags": "科技, AI發展, 未來趨勢"}
        assert ArticleAnalyzer.is_ai_related(article) is True

    def test_is_ai_related_by_tags_keyword_list(self):
        """測試文章標籤（列表）包含AI關鍵字時，is_ai_related 應返回 True"""
        article = {"tags": ["科技", "AI倫理", "創新"]}
        assert ArticleAnalyzer.is_ai_related(article) is True

    def test_is_ai_related_by_content_keywords_above_threshold(self):
        """測試文章內容包含足夠的AI關鍵字時，is_ai_related 應返回 True"""
        article = {
            "content": "本文討論了人工智能、大型語言模型、機器學習和深度學習的最新進展，以及在各行業的應用。"
        }
        assert ArticleAnalyzer.is_ai_related(article) is True

    def test_is_ai_related_by_content_keywords_below_threshold(self):
        """測試文章內容包含的AI關鍵字不足時，is_ai_related 應返回 False"""
        article = {"content": "這是一篇關於軟體開發的文章，提到了演算法和資料結構。"}
        assert ArticleAnalyzer.is_ai_related(article) is False

    def test_is_ai_related_no_ai_info(self):
        """測試文章不包含任何AI相關資訊時，is_ai_related 應返回 False"""
        article = {
            "category": "生活",
            "title": "週末好去處",
            "tags": ["旅遊", "美食"],
            "content": "今天天氣晴朗，適合出遊。",
        }
        assert ArticleAnalyzer.is_ai_related(article) is False

    def test_is_ai_related_check_content_false(self):
        """測試 check_content 為 False 時，即使內容包含足夠關鍵字也可能返回 False"""
        article_with_ai_content = {
            "title": "無關標題",
            "content": "機器學習 深度學習 人工智慧",
        }
        assert (
            ArticleAnalyzer.is_ai_related(article_with_ai_content, check_content=False)
            is False
        )
        article_with_ai_category = {"category": "ai", "content": "無關內容"}
        assert (
            ArticleAnalyzer.is_ai_related(article_with_ai_category, check_content=False)
            is True
        )
        article_with_ai_title = {"title": "AI應用", "content": "無關內容"}
        assert (
            ArticleAnalyzer.is_ai_related(article_with_ai_title, check_content=False)
            is True
        )
        article_with_ai_tag = {"tags": ["科技", "人工智慧"], "content": "無關內容"}
        assert (
            ArticleAnalyzer.is_ai_related(article_with_ai_tag, check_content=False)
            is True
        )

    def test_analyze_articles_statistics_basic(self):
        """測試 analyze_articles_statistics 的基本統計資訊"""
        data = {
            "title": ["AI文章1", "科技文章", "AI文章2"],
            "content": ["機器學習的應用", "軟體開發流程", "深度學習模型"],
            "category": ["AI", "Tech", "AI"],
            "content_length": [10, 8, 12],
        }
        df = pd.DataFrame(data)
        stats = ArticleAnalyzer.analyze_articles_statistics(df)
        assert stats["total_articles"] == 3
        assert stats["avg_article_length"] == 10

    def test_analyze_articles_statistics_category_distribution(self):
        """測試 analyze_articles_statistics 的分類分布統計"""
        data = {
            "title": ["A", "B", "C", "D"],
            "category": ["AI", "Tech", "AI", "AI"],
            "content": ["a", "b", "c", "d"],
        }
        df = pd.DataFrame(data)
        stats = ArticleAnalyzer.analyze_articles_statistics(df)
        assert stats["category_distribution"]["AI"] == 3
        assert stats["category_distribution"]["Tech"] == 1

    def test_analyze_articles_statistics_ai_keyword_frequency(self):
        """測試 analyze_articles_statistics 的AI關鍵字頻率統計 (ai_only=True)"""
        data = {
            "title": ["AI文章"],
            "content": ["機器學習 深度學習 人工智慧"],
            "category": ["AI"],
        }
        df = pd.DataFrame(data)
        stats = ArticleAnalyzer.analyze_articles_statistics(df, ai_only=True)
        expected_keywords = {
            keyword: 1
            for keyword in ["機器學習", "深度學習", "人工智慧"]
            if keyword in AI_KEYWORDS
        }
        for keyword, count in expected_keywords.items():
            assert stats["ai_keyword_frequency"].get(keyword) == count

    def test_analyze_articles_statistics_ai_keyword_frequency_not_ai_only(self):
        """測試 analyze_articles_statistics 的AI關鍵字頻率統計 (ai_only=False)"""
        data = {
            "title": ["AI文章", "科技文章"],
            "content": ["機器學習", "演算法"],
            "category": ["AI", "Tech"],
        }
        df = pd.DataFrame(data)
        stats = ArticleAnalyzer.analyze_articles_statistics(df, ai_only=False)
        assert "ai_keyword_frequency" not in stats

    def test_analyze_articles_statistics_empty_dataframe(self):
        """測試 analyze_articles_statistics 處理空 DataFrame 的情況"""
        df = pd.DataFrame()
        stats = ArticleAnalyzer.analyze_articles_statistics(df)
        assert stats["total_articles"] == 0
        assert "avg_article_length" not in stats
        assert "category_distribution" not in stats
        assert "ai_keyword_frequency" not in stats

    def test_analyze_articles_statistics_missing_columns(self):
        """測試 analyze_articles_statistics 處理缺少欄位的 DataFrame"""
        data_no_content_length = {"title": ["A"], "content": ["abc"]}
        df_no_content_length = pd.DataFrame(data_no_content_length)
        stats_no_length = ArticleAnalyzer.analyze_articles_statistics(
            df_no_content_length
        )
        assert "avg_article_length" not in stats_no_length

        data_no_category = {"title": ["A"], "content": ["abc"]}
        df_no_category = pd.DataFrame(data_no_category)
        stats_no_category = ArticleAnalyzer.analyze_articles_statistics(df_no_category)
        assert "category_distribution" not in stats_no_category

        data_no_content = {"title": ["A"], "category": ["AI"]}
        df_no_content = pd.DataFrame(data_no_content)
        stats_no_content = ArticleAnalyzer.analyze_articles_statistics(
            df_no_content, ai_only=True
        )
        assert "ai_keyword_frequency" not in stats_no_content
