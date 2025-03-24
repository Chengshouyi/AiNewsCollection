import pandas as pd
import os

from src.crawlers.bnext_scraper import BnextScraper
from src.crawlers.bnext_content_extractor import BnextContentExtractor


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
    
    # 初始化資料庫管理器
    from src.database.database_manager import DatabaseManager
    db_manager = DatabaseManager()
    
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
        scraper = BnextScraper(db_manager)
        
        if category:
            # 爬取特定分類
            categories = [f"https://www.bnext.com.tw/categories/{category}"]
            articles_df = scraper.scrape_article_list(max_pages=pages, categories=categories, ai_only=ai_only)
        else:
            # 爬取所有預設分類
            articles_df = scraper.scrape_article_list(max_pages=pages, ai_only=ai_only)
    
    # 如果沒有爬取到任何文章，則退出
    if articles_df.empty:
        print("未找到任何文章，程序結束")
        return
    
    # 如果要爬取文章內容
    if content:
        extractor = BnextContentExtractor()
        articles_df = extractor.batch_get_articles_content(
            articles_df, 
            num_articles=content_limit, 
            ai_only=ai_only,
            min_keywords=min_keywords,
            db_manager=db_manager
        )
    
    # 如果要分析文章統計資訊
    if analyze:
        analyze_articles_statistics(articles_df, ai_only=ai_only)
    
    print("\n爬蟲程序執行完畢")

def analyze_articles_statistics(articles_df, ai_only=True):
    """
    分析文章統計資訊
    
    Args:
        articles_df: 文章DataFrame
        ai_only: 是否只分析AI相關文章
    """
    print("\n===== 文章統計分析 =====")
    print(f"總文章數: {len(articles_df)}")
    
    # 分類統計
    if 'category' in articles_df.columns:
        category_counts = articles_df['category'].value_counts()
        print("\n分類統計:")
        for category, count in category_counts.items():
            print(f"  {category}: {count}篇")
    
    # 標籤統計
    if 'tags' in articles_df.columns:
        all_tags = []
        for tags_str in articles_df['tags'].dropna():
            if isinstance(tags_str, str):
                tags = [tag.strip() for tag in tags_str.split(',')]
                all_tags.extend(tags)
        
        if all_tags:
            from collections import Counter
            tag_counts = Counter(all_tags)
            print("\n熱門標籤:")
            for tag, count in tag_counts.most_common(10):
                print(f"  {tag}: {count}次")
    
    # 作者統計
    if 'author' in articles_df.columns:
        author_counts = articles_df['author'].value_counts()
        print("\n作者統計:")
        for author, count in author_counts.head(10).items():
            if author and not pd.isna(author):
                print(f"  {author}: {count}篇")
    
    print("========================")

if __name__ == "__main__":
    main(pages=1, category=None, all=False, content=False, content_limit=1, min_keywords=3, input_file=None, analyze=False)



"""from src.model.database_manager import DatabaseManager
from src.crawler.bnext_scraper import BnextScraper
from src.crawler.bnext_content_extractor import BnextContentExtractor

# 初始化資料庫管理器
db_manager = DatabaseManager()

# 爬取文章列表
scraper = BnextScraper(db_manager)
articles_df = scraper.scrape_article_list(max_pages=2, ai_only=True)

# 爬取文章詳細內容
extractor = BnextContentExtractor()
contents_df = extractor.batch_get_articles_content(articles_df, num_articles=5, ai_only=True, db_manager=db_manager)
"""