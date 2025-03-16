# article_analyzer.py
# 用於分析文章是否與AI相關的

import pandas as pd
from src.crawler.ai_filter_config import AI_KEYWORDS, AI_CATEGORIES

class ArticleAnalyzer:
    def __init__(self):
        pass

    def is_ai_related(self, article_info, min_keywords=3, check_content=True):
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
        if article_info.get('category'):
            category_lower = str(article_info['category']).lower()
            if any(ai_cat in category_lower for ai_cat in AI_CATEGORIES):
                return True
        
        # 2. 檢查標題是否包含AI關鍵字
        if article_info.get('title'):
            title_lower = str(article_info['title']).lower()
            if any(keyword in title_lower for keyword in AI_KEYWORDS):
                return True
        
        # 3. 檢查標籤是否包含AI關鍵字
        if article_info.get('tags') and isinstance(article_info['tags'], list):
            tags_lower = [tag.lower() for tag in article_info['tags']]
            if any(any(keyword in tag for keyword in AI_KEYWORDS) for tag in tags_lower):
                return True
        
        # 4. 檢查內容是否包含足夠的AI關鍵字
        if check_content and article_info.get('content'):
            content_lower = str(article_info['content']).lower()
            keyword_count = sum(1 for keyword in AI_KEYWORDS if keyword in content_lower)
            if keyword_count >= min_keywords:
                return True
        
        return False

    def analyze_articles_statistics(self, articles_df, ai_only=True):
        """
        分析文章統計數據
        
        Parameters:
        articles_df (pandas.DataFrame): 文章數據框
        ai_only (bool): 是否只分析AI相關文章
        
        Returns:
        None: 在控制台輸出分析結果
        """
        # 輸出基本統計資訊
        print("\n基本統計資訊:")
        print(f"總文章數: {len(articles_df)}")
        
        # 計算平均文章長度
        if 'content_length' in articles_df.columns:
            avg_length = articles_df['content_length'].mean()
            print(f"平均文章長度: {avg_length:.2f} 字符")
        
        # 統計分類分布
        if 'category' in articles_df.columns:
            category_counts = articles_df['category'].value_counts()
            print("\n分類分布:")
            for cat, count in category_counts.items():
                if pd.notna(cat):
                    print(f"  {cat}: {count} 篇")
        
        # 輸出AI關鍵字統計
        if ai_only and 'content' in articles_df.columns:
            print("\nAI關鍵字出現頻率:")
            keyword_counts = {}
            for _, row in articles_df.iterrows():
                content = str(row['content']).lower()
                for keyword in AI_KEYWORDS:
                    if keyword in content:
                        keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
            
            # 排序並顯示前20個最常出現的關鍵字
            sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            for keyword, count in sorted_keywords:
                print(f"  {keyword}: {count} 篇")
