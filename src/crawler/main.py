# main.py
# 程式主入口點

import argparse
import pandas as pd
import os

from src.crawler.bnext_scraper import BnextScraper
from src.crawler.bnext_content_extractor import BnextContentExtractor
from src.crawler.article_analyzer import ArticleAnalyzer
from src.crawler.ai_filter_config import AI_KEYWORDS, AI_CATEGORIES


def main(pages=3, category=None, all=False, content=False, content_limit=10, min_keywords=3, input_file=None, analyze=False):
    """
    pages：type=int, default=3, 爬取的最大頁數
    category：type=str, 指定爬取特定分類的URL
    all：type=bool, action='store_true, 爬取所有文章，不僅限於AI相關
    content：type=bool, action='store_true, 爬取文章內容
    content_limit：type=int, default=10, 爬取內容的文章數量上限
    min_keywords：type=int, default=3, 判定為AI相關文章的最少關鍵字數量
    input_file：type=str, 使用已有的CSV文件作為輸入
    analyze：type=bool, action='store_true, 分析爬取的文章統計資訊
    """
    # 確定是否只爬取AI相關文章
    ai_only = not all
    
    # 如果指定了輸入文件，則從文件讀取
    if input_file:
        if not os.path.exists(input_file):
            print(f"錯誤：找不到輸入文件 {input_file}")
            return
        
        try:
            articles_df = pd.read_csv(input_file, encoding='utf-8-sig')
            print(f"已從 {input_file} 讀取 {len(articles_df)} 篇文章信息")
        except Exception as e:
            print(f"讀取輸入文件時發生錯誤：{e}")
            return
    else:
        # 否則，爬取新的文章
        if category:
            # 爬取特定分類
            articles_df = scrape_single_category(category, max_pages=pages, ai_only=ai_only)
        else:
            # 爬取所有預設分類
            articles_df = scrape_bnext_tech_articles(max_pages=pages, ai_only=ai_only)
    
    # 如果沒有爬取到任何文章，則退出
    if articles_df.empty:
        print("未找到任何文章，程序結束")
        return
    
    # 如果要爬取文章內容
    if content:
        articles_df = batch_get_articles_content(
            articles_df, 
            num_articles=content_limit, 
            ai_only=ai_only,
            min_keywords=min_keywords
        )
    
    # 如果要分析文章統計資訊
    if analyze:
        analyze_articles_statistics(articles_df, ai_only=ai_only)
    
    print("\n爬蟲程序執行完畢")

if __name__ == "__main__":
    main(pages=1, category=None, all=False, content=False, content_limit=1, min_keywords=3, input_file=None, analyze=False)
