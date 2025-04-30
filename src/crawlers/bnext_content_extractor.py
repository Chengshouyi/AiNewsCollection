"""Bnext 數位時代文章內容提取器"""
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any

import pandas as pd
import requests

from src.crawlers.article_analyzer import ArticleAnalyzer
from src.crawlers.bnext_utils import BnextUtils
from src.crawlers.configs.base_config import DEFAULT_HEADERS
from src.utils import datetime_utils
from src.utils.enum_utils import ArticleScrapeStatus


logger = logging.getLogger(__name__)  # 使用統一的 logger


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

    def batch_get_articles_content(self, articles_df: pd.DataFrame, num_articles: Optional[int] = None,
                                   ai_only: bool = True, min_keywords: int = 3, is_limit_num_articles: bool = False) -> List[Dict[str, Any]]:
        """批量獲取文章內容

        Args:
            articles_df: 文章DataFrame
            num_articles: 最大處理文章數量，None表示處理所有
            ai_only: 是否只處理AI相關文章
            min_keywords: AI關鍵字最小匹配數量
            is_limit_num_articles: 是否限制處理文章的數量

        Returns:
            List[Dict[str, Any]]: 文章內容列表
        """
        result = []

        # 如果限制數量，只處理指定數量的文章
        if is_limit_num_articles and num_articles is not None and num_articles > 0:
            articles_df = articles_df.head(num_articles)

        for _, article in articles_df.iterrows():
            article_link = article['link']
            article_title = article.get('title', '')
            try:
                # 獲取文章內容
                # 傳遞 ai_only 和 min_keywords 給 _get_article_content
                article_content = self._get_article_content(article_link, ai_only=ai_only, min_keywords=min_keywords)
                logger.debug("處理文章: %s, 結果: %s", article_link, "成功" if article_content else "失敗")

                if article_content:
                    # 檢查是否已經有 scrape_status，如果文章因為非 AI 相關而被標記，則直接使用該記錄
                    if 'scrape_status' in article_content and article_content['scrape_status'] == ArticleScrapeStatus.CONTENT_SCRAPED.value and article_content.get('scrape_error') == "文章不符合 AI 相關條件":
                         # logger.debug(f"文章非 AI 相關，使用已標記的記錄: {article_link}")
                        pass # 直接使用 article_content
                    else:
                        # 更新成功抓取的文章狀態
                        article_content.update({
                            'is_scraped': True,
                            'scrape_status': ArticleScrapeStatus.CONTENT_SCRAPED.value,
                            'scrape_error': None,
                            'last_scrape_attempt': datetime.now(timezone.utc)
                        })
                    result.append(article_content)
                else:
                    # 如果 _get_article_content 返回 None (通常是請求失敗或找不到容器)
                    logger.warning("無法獲取文章內容: %s", article_link)
                    result.append({
                        'title': article_title,
                        'link': article_link,
                        'is_scraped': False,
                        'scrape_status': ArticleScrapeStatus.FAILED.value,
                        'scrape_error': '無法獲取文章內容 (請求失敗或找不到容器)',
                        'last_scrape_attempt': datetime.now(timezone.utc)
                    })
            except Exception as e:
                logger.error("處理文章時發生未知錯誤: %s, 錯誤: %s", article_link, str(e), exc_info=True)
                # 處理抓取過程中的其他異常
                result.append({
                    'title': article_title,
                    'link': article_link,
                    'is_scraped': False,
                    'scrape_status': ArticleScrapeStatus.FAILED.value,
                    'scrape_error': f'處理文章時發生未知錯誤: {str(e)}',
                    'last_scrape_attempt': datetime.now(timezone.utc)
                })

        return result

    def _get_article_content(self, article_url: str, ai_only: bool = True, min_keywords: int = 3) -> Optional[Dict]:
        """獲取文章詳細內容"""
        logger.debug("開始獲取文章內容: %s", article_url)
        start_time = time.time()

        try:
            BnextUtils.sleep_random_time(2.0, 4.0)

            response = requests.get(article_url, headers=DEFAULT_HEADERS, timeout=15)
            if response.status_code != 200:
                logger.error("請求失敗 (%s): %s", response.status_code, article_url)
                return None

            logger.debug("成功獲取網頁內容: %s", article_url)

            soup = BnextUtils.get_soup_from_html(response.text)
            if self.site_config is None or not hasattr(self.site_config, 'selectors') or 'get_article_contents' not in self.site_config.selectors:
                logger.error("網站配置或選擇器未正確設定")
                raise ValueError("網站配置或選擇器未正確設定")

            selectors = self.site_config.selectors
            get_article_contents_selectors = selectors.get('get_article_contents')

            content_container_selector = get_article_contents_selectors.get("content_container")
            if not content_container_selector:
                 logger.error("缺少 'content_container' 選擇器配置: %s", article_url)
                 return None

            # 提取文章內容
            article_content_container = soup.select_one(content_container_selector) # 使用 select_one 获取单个容器
            if not article_content_container:
                logger.error("無法找到文章 container 使用選擇器 '%s': %s", content_container_selector, article_url)
                return None

            # 傳遞單個容器元素而非列表
            article_data = self._extract_article_parts(article_content_container, soup, get_article_contents_selectors, article_url)

            if article_data is None:
                logger.error("文章內容提取失敗 (可能缺少必要部分): %s", article_url)
                return None # _extract_article_parts 内部已记录错误

            # AI 相關性檢查 - 僅在需要時執行
            if ai_only:
                is_ai_related = ArticleAnalyzer().is_ai_related(article_data, min_keywords=min_keywords)
                logger.debug("AI相關性檢查 (%s 最小匹配關鍵字數): %s - %s", min_keywords, '通過' if is_ai_related else '未通過', article_url)
                article_data['is_ai_related'] = is_ai_related # 記錄檢查結果
                if not is_ai_related:
                    # 如果文章不相關，更新狀態並返回，不再繼續處理
                    article_data.update({
                        'is_scraped': True, # 標記為已抓取，即使內容不符條件
                        'scrape_status': ArticleScrapeStatus.CONTENT_SCRAPED.value,
                        'scrape_error': "文章不符合 AI 相關條件",
                        'last_scrape_attempt': datetime.now(timezone.utc)
                    })
                    # 注意：這裡返回 article_data，而不是 None，以便 batch 方法可以記錄此狀態
                    return article_data
            else:
                 # 如果不限制 AI，則標記為 True (或根據需求設為 None/False)
                 article_data['is_ai_related'] = True # 或者根據實際情況賦值

            # 更新成功抓取的狀態 (如果通過了 AI 檢查或不需要檢查)
            article_data.update({
                'is_scraped': True,
                'scrape_status': ArticleScrapeStatus.CONTENT_SCRAPED.value,
                'scrape_error': None,
                'last_scrape_attempt': datetime.now(timezone.utc)
            })

            end_time = time.time()
            logger.debug("文章內容獲取完成，耗時: %.2f秒 - %s", end_time - start_time, article_url)

            return article_data

        except requests.exceptions.RequestException as e:
            logger.error("請求文章時發生錯誤: %s, URL: %s", str(e), article_url, exc_info=True)
            return None # 返回 None 表示請求階段失敗
        except ValueError as e:
             logger.error("配置錯誤: %s, URL: %s", str(e), article_url, exc_info=True)
             # 配置錯誤可能影響後續，但這裡返回 None 讓 batch 處理
             return None
        except Exception as e:
            # 捕獲其他所有未預料的錯誤
            logger.error("獲取文章內容時發生未知錯誤: %s, URL: %s", str(e), article_url, exc_info=True)
            return None # 返回 None 表示處理失敗

    def _extract_article_parts(self, article_content_container, soup, get_article_contents_selectors, article_url: str):
        """提取文章各個部分"""
        logger.debug("開始提取文章各部分內容: %s", article_url)

        if not article_content_container:
            logger.error("沒有提供文章 container: %s", article_url)
            return None

        try:
            # 提取各個部分並記錄日誌
            category_selector = get_article_contents_selectors.get("category")
            category = article_content_container.select_one(category_selector) if category_selector else None
            category_text = category.get_text(strip=True) if category else None
            logger.debug("提取文章 category: %s - %s", category_text, article_url)

            published_date_selector = get_article_contents_selectors.get("published_date")
            published_date = article_content_container.select_one(published_date_selector) if published_date_selector else None
            published_date_text = published_date.get_text(strip=True) if published_date else None
            logger.debug("提取文章 published_date: %s - %s", published_date_text, article_url)
            published_date_iso = None
            if published_date_text:
                try:
                    published_date_iso = datetime_utils.convert_str_to_utc_ISO_str(published_date_text)
                    logger.debug("轉換文章 published_date: %s - %s", published_date_iso, article_url)
                except Exception as e:
                    logger.error("日期格式轉換錯誤 '%s': %s - %s", published_date_text, str(e), article_url, exc_info=True)
                    # 保留 None

            title_selector = get_article_contents_selectors.get("title")
            title = article_content_container.select_one(title_selector) if title_selector else None
            title_text = title.get_text(strip=True) if title else None
            logger.debug("提取文章 title: %s - %s", title_text, article_url)

            summary_selector = get_article_contents_selectors.get("summary")
            summary = article_content_container.select_one(summary_selector) if summary_selector else None
            summary_text = summary.get_text(strip=True) if summary else None
            logger.debug("提取文章 summary: %s - %s", summary_text[:100] if summary_text else None, article_url)

            # 提取標籤
            tags = []
            tags_config = get_article_contents_selectors.get("tags", {})
            tag_container_selector = tags_config.get("container")
            tag_selector = tags_config.get("tag")
            if tag_container_selector and tag_selector:
                tag_container = article_content_container.select_one(tag_container_selector)
                if tag_container:
                    logger.debug("找到標籤容器 - %s", article_url)
                    for tag_element in tag_container.select(tag_selector):
                        tag_text = tag_element.get_text(strip=True)
                        if tag_text:
                            logger.debug("找到 Tag: %s - %s", tag_text, article_url)
                            tags.append(tag_text)
                else:
                    logger.debug("未找到標籤容器使用選擇器 '%s' - %s", tag_container_selector, article_url)
            else:
                logger.debug("缺少標籤選擇器配置 ('container' 或 'tag') - %s", article_url)

            author_selector = get_article_contents_selectors.get("author")
            author = article_content_container.select_one(author_selector) if author_selector else None
            # Bnext 作者可能有多個 <a> 標籤，需要提取所有作者名字
            authors_list = []
            if author_selector and article_content_container.select(author_selector):
                author_elements = article_content_container.select(author_selector)
                for auth_elem in author_elements:
                    name = auth_elem.get_text(strip=True)
                    if name:
                        authors_list.append(name)
            author_text = ",".join(authors_list) if authors_list else (author.get_text(strip=True) if author else None)
            logger.debug('提取 author: %s - %s', author_text, article_url)

            # 提取內容
            full_content = ""
            content_selector = get_article_contents_selectors.get("content")
            if content_selector:
                content_container = soup.select_one(content_selector) # 從 soup 根節點查找內容容器可能更穩定
                if content_container:
                    all_text = []
                    # 提取常見的文本塊標籤
                    for element in content_container.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'span', 'div'], recursive=True):
                        # 避免提取腳本、樣式或特定不需要的 class
                        if element.name in ['script', 'style'] or (hasattr(element, 'get') and element.get('class') and any(c in ['ad', 'advertisement', 'related-articles'] for c in element.get('class'))):
                            continue
                        text = element.get_text(separator=' ', strip=True)
                        if text:
                            all_text.append(text)
                    # 使用換行符連接，並去除重複的空行
                    full_content = "\n".join(filter(None, all_text))
                    logger.debug('提取 content (前 100 字): %s... - %s', full_content[:100], article_url)

                    # 如果沒有提取到內容，記錄警告
                    if not full_content:
                        logger.warning("使用選擇器 '%s' 提取到的內容為空 - %s", content_selector, article_url)

                    # 使用提取的內容填充缺失的標題、摘要、分類
                    if summary_text is None and full_content:
                        summary_text = full_content[:200] # 增加摘要長度
                        logger.debug("文章摘要為空，使用內容前 200 字作為摘要 - %s", article_url)
                    if title_text is None and full_content:
                        title_text = full_content[:60] # 增加標題長度
                        logger.debug("文章標題為空，使用內容前 60 字作為標題 - %s", article_url)
                    if category_text is None:
                        category_text = "未分類"
                        logger.debug("文章分類為空，使用「未分類」作為分類 - %s", article_url)
                else:
                    logger.error("找不到文章內容容器使用選擇器 '%s' - %s", content_selector, article_url)
                    # 即使找不到內容，也嘗試返回其他提取的部分
            else:
                logger.error("缺少 'content' 選擇器配置 - %s", article_url)
                # 即使沒有內容選擇器，也嘗試返回其他提取的部分

            # 返回提取的所有部分 (創建基礎字典，後續在 _get_article_content 中更新狀態)
            return BnextUtils.get_article_columns_dict(
                title=title_text,
                summary=summary_text,
                content=full_content,
                link=article_url,
                category=category_text,
                published_at=published_date_iso, # 使用轉換後的 ISO 格式日期
                author=author_text,
                source=self.site_config.name,
                source_url=self.site_config.base_url,
                article_type=None,
                tags=",".join(tags) if tags else None,
                is_ai_related=None, # AI 相關性將在調用者中設置
                is_scraped=None, # 抓取狀態將在調用者中設置
                scrape_status=None, # 抓取狀態將在調用者中設置
                scrape_error=None,
                last_scrape_attempt=None,
                task_id=None
            )

        except Exception as e:
            logger.error("提取文章部分時發生錯誤: %s - %s", str(e), article_url, exc_info=True)
            # 返回 None 表示提取失敗
            return None
