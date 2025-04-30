"""提供文章分析相關功能，特別是判斷文章是否與 AI 相關以及統計分析。"""

from typing import Dict, Any
import logging

import pandas as pd

from src.crawlers.configs.ai_filter_config import AI_KEYWORDS, AI_CATEGORIES
  # 使用統一的 logger

logger = logging.getLogger(__name__)  # 使用統一的 logger  # 使用統一的 logger


class ArticleAnalyzer:
    """處理文章AI內容相關性分析的類別"""

    @staticmethod
    def is_ai_related(
        article_info: Dict[str, Any], min_keywords: int = 3, check_content: bool = True
    ) -> bool:
        """
        判斷文章是否與AI相關

        Parameters:
        article_info (dict): 包含文章信息的字典
        min_keywords (int): 文章內容中最少需要包含的AI關鍵字數量
        check_content (bool): 是否檢查文章內容

        Returns:
        bool: 如果文章與AI相關，則返回True；否則返回False
        """
        # 1. 檢查分類是否AI相關
        if article_info.get("category"):
            category_lower = str(article_info["category"]).lower()
            if any(ai_cat in category_lower for ai_cat in AI_CATEGORIES):
                return True

        # 2. 檢查標題是否包含AI關鍵字
        if article_info.get("title"):
            title_lower = str(article_info["title"]).lower()
            if any(keyword in title_lower for keyword in AI_KEYWORDS):
                return True

        # 3. 檢查標籤是否包含AI關鍵字
        if article_info.get("tags"):
            tags = article_info["tags"]
            # 處理標籤可能是列表或字符串的情況
            if isinstance(tags, str) and tags:
                tags_list = [tag.strip().lower() for tag in tags.split(",")]
                if any(
                    any(keyword in tag for keyword in AI_KEYWORDS) for tag in tags_list
                ):
                    return True
            elif isinstance(tags, list):
                tags_lower = [tag.lower() for tag in tags]
                if any(
                    any(keyword in tag for keyword in AI_KEYWORDS) for tag in tags_lower
                ):
                    return True

        # 4. 檢查內容是否包含足夠的AI關鍵字
        if check_content and article_info.get("content"):
            content_lower = str(article_info["content"]).lower()
            keyword_count = sum(
                1 for keyword in AI_KEYWORDS if keyword in content_lower
            )
            if keyword_count >= min_keywords:
                return True

        return False

    @staticmethod
    def analyze_articles_statistics(
        articles_df: pd.DataFrame, ai_only: bool = True
    ) -> Dict[str, Any]:
        """
        分析文章統計數據

        Parameters:
        articles_df (pandas.DataFrame): 文章數據框
        ai_only (bool): 是否只分析AI相關文章

        Returns:
        Dict[str, Any]: 包含分析結果的字典
        """
        # 獲取基本統計資訊
        stats: Dict[str, Any] = {"total_articles": len(articles_df)}

        # 計算平均文章長度
        if "content_length" in articles_df.columns:
            avg_length = articles_df["content_length"].mean()
            stats["avg_article_length"] = int(round(avg_length, 2))

        # 統計分類分布
        if "category" in articles_df.columns:
            category_counts = articles_df["category"].value_counts().to_dict()
            stats["category_distribution"] = category_counts

        # 統計AI關鍵字出現頻率
        if ai_only and "content" in articles_df.columns:
            keyword_counts = {}
            for _, row in articles_df.iterrows():
                content = str(row["content"]).lower()
                for keyword in AI_KEYWORDS:
                    if keyword in content:
                        keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

            # 排序並獲取前20個最常出現的關鍵字
            sorted_keywords = sorted(
                keyword_counts.items(), key=lambda x: x[1], reverse=True
            )[:20]
            stats["ai_keyword_frequency"] = dict(sorted_keywords)

        return stats

    @staticmethod
    def print_statistics(stats: Dict[str, Any]) -> None:
        """輸出統計數據到日誌"""
        logger.debug("基本統計資訊:")
        logger.debug("總文章數: %s", stats["total_articles"])

        if "avg_article_length" in stats:
            logger.debug("平均文章長度: %s 字符", stats["avg_article_length"])

        if "category_distribution" in stats:
            logger.debug("分類分布:")
            for cat, count in stats["category_distribution"].items():
                if pd.notna(cat):
                    logger.debug("  %s: %s 篇", cat, count)

        if "ai_keyword_frequency" in stats:
            logger.debug("AI關鍵字出現頻率:")
            for keyword, count in stats["ai_keyword_frequency"].items():
                logger.debug("  %s: %s 篇", keyword, count)
