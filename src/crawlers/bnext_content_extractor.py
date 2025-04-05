import requests
import logging
from typing import Dict, Optional, List, Any
import pandas as pd

import time

from src.crawlers.configs.base_config import DEFAULT_HEADERS
from src.crawlers.article_analyzer import ArticleAnalyzer
from src.crawlers.bnext_utils import BnextUtils
from src.utils.log_utils import LoggerSetup

# 設置日誌記錄器(校正用)
# custom_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# logger = LoggerSetup.setup_logger(
#     module_name='bnext_content_extractor',
#     log_dir='logs',  # 這會在專案根目錄下創建 logs 目錄
#     log_format=custom_format,
#     level=logging.DEBUG,
#     date_format='%Y-%m-%d %H:%M:%S'
# )
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BnextContentExtractor:
    def __init__(self, config=None):
        """
        初始化爬蟲設定
        """
        if config is None:
            logger.error("未提供網站配置，請提供有效的配置")
            raise ValueError("未提供網站配置，請提供有效的配置")
        else:
            self.site_config = config
            
    def update_config(self, config=None):
        """
        更新爬蟲設定
        """
        if config is None:
            logger.error("未提供網站配置，請提供有效的配置")
            raise ValueError("未提供網站配置，請提供有效的配置")
        else:
            self.site_config = config

    def batch_get_articles_content(self, articles_df, num_articles=10, ai_only=True, min_keywords=3) -> List[Dict[str, Any]]:
        """批量獲取文章內容"""
        start_time = time.time()
        
        logger.debug("開始批量獲取文章內容")
        logger.debug(f"參數設置: num_articles={num_articles}, ai_only={ai_only}, min_keywords={min_keywords}")
        logger.debug(f"待處理文章數量: {len(articles_df)}")
        
        article_contents = []
        successful_count = 0
        ai_related_count = 0
        failed_count = 0
        
        try:
            for i, (_, article) in enumerate(articles_df.head(num_articles).iterrows(), 1):
                logger.debug(f"處理第 {i}/{num_articles} 篇文章")
                logger.debug(f"文章標題: {article['title']}")
                logger.debug(f"文章連結: {article['link']}")
                
                try:
                    content_data = self._get_article_content(
                        article['link'], 
                        ai_filter=ai_only, 
                        min_keywords=min_keywords
                    )
                    
                    if content_data is None:
                        failed_count += 1
                        logger.warning(f"文章內容獲取失敗或不符合AI相關條件: {article['title']}")
                        continue
                    
                    article_contents.append(content_data)
                    successful_count += 1
                    ai_related_count += 1
                    
                    # 記錄進度
                    if successful_count % 5 == 0:
                        elapsed_time = time.time() - start_time
                        avg_time = elapsed_time / successful_count
                        logger.debug(f"進度報告:")
                        logger.debug(f"- 已處理: {i}/{num_articles}")
                        logger.debug(f"- 成功數: {successful_count}")
                        logger.debug(f"- AI相關: {ai_related_count}")
                        logger.debug(f"- 失敗數: {failed_count}")
                        logger.debug(f"- 平均處理時間: {avg_time:.2f}秒/篇")
                
                except Exception as e:
                    failed_count += 1
                    logger.error(f"處理文章時發生錯誤: {str(e)}", exc_info=True)
        
        finally:
            # 最終統計
            end_time = time.time()
            total_time = end_time - start_time
            
            logger.debug("爬取任務完成")
            logger.debug(f"總耗時: {total_time:.2f}秒")
            logger.debug(f"處理統計:")
            logger.debug(f"- 總處理文章: {num_articles}")
            logger.debug(f"- 成功獲取: {successful_count}")
            logger.debug(f"- AI相關文章: {ai_related_count}")
            logger.debug(f"- 處理失敗: {failed_count}")
            if successful_count > 0:
                logger.debug(f"- 平均處理時間: {total_time/successful_count:.2f}秒/篇")
        
        return article_contents



    def _get_article_content(self, article_url: str, ai_filter: bool = True, min_keywords: int = 3) -> Optional[Dict]:
        """獲取文章詳細內容"""
        logger.debug(f"開始獲取文章內容: {article_url}")
        start_time = time.time()
        
        try:
            BnextUtils.sleep_random_time(2.0, 4.0)
            
            response = requests.get(article_url, headers=DEFAULT_HEADERS, timeout=15)
            if response.status_code != 200:
                logger.error(f"請求失敗 ({response.status_code}): {article_url}")
                return None
            
            logger.debug("成功獲取網頁內容")
            
            soup = BnextUtils.get_soup_from_html(response.text)
            if self.site_config is None:
                logger.error("未提供選擇器，請提供有效的配置")
                raise ValueError("未提供選擇器，請提供有效的配置")
            
            selectors = self.site_config.selectors
            get_article_contents_selectors = selectors.get('get_article_contents')
            #logger.debug(f"get_article_contents_selectors: {get_article_contents_selectors}")

            # 提取文章內容
            article_content_container = soup.select(get_article_contents_selectors.get("content_container"))
            if not article_content_container:
                logger.error(f"無法找到文章container: {article_url}")
                return None
            #logger.debug(f"article_content_container: {article_content_container}")
            article_content = self._extract_article_parts(article_content_container, soup, get_article_contents_selectors, article_url, ai_filter)
            if article_content is None:
                logger.error(f"文章內容提取失敗: {article_url}")
                return None
            
            # AI 相關性檢查
            if ai_filter:
                is_ai_related = ArticleAnalyzer().is_ai_related(article_content, min_keywords=min_keywords)
                logger.debug(f"AI相關性檢查: {'通過' if is_ai_related else '未通過'}")
                if not is_ai_related:
                    return None
            
            end_time = time.time()
            logger.debug(f"文章內容獲取完成，耗時: {end_time - start_time:.2f}秒")
            
            return article_content
            
        except Exception as e:
            logger.error(f"獲取文章內容失敗: {str(e)}", exc_info=True)
            return None

    def _extract_article_parts(self, article_content_container, soup, get_article_contents_selectors, article_url: str, ai_filter: bool = True):
        """提取文章各個部分"""
        logger.debug("開始提取文章各部分內容")
        
        if not article_content_container:
            logger.error("沒有提供文章container")
            return None
        
        logger.debug(f"找到文章container數量: {len(article_content_container)}")
        
        try:
            # 獲取主要容器以避免重複訪問
            main_container = article_content_container[0]
            
            # 提取各個部分並記錄日誌
            category = main_container.select_one(get_article_contents_selectors.get("category"))
            category_text = category.get_text(strip=True) if category else None
            logger.debug(f"提取文章category: {category_text}")
            
            published_date = main_container.select_one(get_article_contents_selectors.get("published_date"))
            published_date_text = published_date.get_text(strip=True) if published_date else None
            logger.debug(f"提取文章published_date: {published_date_text}")
            
            title = main_container.select_one(get_article_contents_selectors.get("title"))
            title_text = title.get_text(strip=True) if title else None
            logger.debug(f"提取文章title: {title_text}")
            
            summary = main_container.select_one(get_article_contents_selectors.get("summary"))
            summary_text = summary.get_text(strip=True) if summary else None
            logger.debug(f"提取文章summary: {summary_text}")

            # 提取標籤
            tags = []
            tag_container_selector = get_article_contents_selectors.get("tags").get("container")
            tag_container = main_container.select_one(tag_container_selector)
            if not tag_container:
                logger.error("沒有標籤容器")
            else:
                logger.debug(f"找到標籤容器數量: {len(tag_container)}")
                for container in tag_container.find_all(get_article_contents_selectors.get("tags").get("tag"), recursive=False):
                    tag_text = container.get_text(strip=True)
                    logger.debug(f"找到Tag: {tag_text}")
                    tags.append(tag_text)

            author = main_container.select_one(get_article_contents_selectors.get("author"))
            author_text = author.get_text(strip=True) if author else None
            logger.debug(f'提取author: {author_text}')

            # 提取內容
            full_content = ""
            content_container = main_container.select_one(get_article_contents_selectors.get("content"))
            if content_container:
                all_text = []
                for element in content_container.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol']):
                    text = element.get_text(strip=True)
                    if text:
                        all_text.append(text)
                full_content = "\n".join(all_text)
                logger.debug(f'提取content: {full_content[:100]}...') # 只記錄前100個字符
            else:
                logger.error("找不到文章內容容器")
                return None

            # 返回提取的所有部分
            return BnextUtils.get_article_columns_dict(
                title=title_text,
                summary=summary_text,
                content=full_content,
                link=article_url,
                category=category_text,
                published_at=published_date_text,
                author=author_text,
                source=self.site_config.name,
                source_url=self.site_config.base_url,
                article_type=None,
                tags=",".join(tags),
                is_ai_related=ai_filter,
                is_scraped=True
            )
            
        except Exception as e:
            logger.error(f"提取文章部分時發生錯誤: {str(e)}", exc_info=True)
            return None

