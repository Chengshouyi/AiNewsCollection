# content_extractor.py
# 用於爬取文章內容的模組

import requests
import logging
from typing import Dict, Optional, List
import pandas as pd
import re
import time
from datetime import datetime

from src.crawlers.base_config import DEFAULT_HEADERS
from src.crawlers.bnext_config import BNEXT_CONFIG
from src.crawlers.article_analyzer import ArticleAnalyzer
from src.crawlers.bnext_utils import BnextUtils
from src.utils.log_utils import LoggerSetup

# 設置日誌記錄器
custom_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logger = LoggerSetup.setup_logger(
    module_name='bnext_content_extractor',
    log_dir='logs',  # 這會在專案根目錄下創建 logs 目錄
    log_format=custom_format,
    level=logging.DEBUG,
    date_format='%Y-%m-%d %H:%M:%S'
)

class BnextContentExtractor:
    def __init__(self):
        self.article_repository = None
        logger.info("初始化 BnextContentExtractor")
        
    def set_db_manager(self, db_manager):
        """設置資料庫管理器"""
        logger.info("設置資料庫管理器")
        self.db_manager = db_manager
        if db_manager:
            self.article_repository = db_manager.get_repository('Article')
            logger.info("成功獲取 Article Repository")
        else:
            logger.warning("未提供資料庫管理器")

    def batch_get_articles_content(self, articles_df, num_articles=10, ai_only=True, min_keywords=3, db_manager=None) -> pd.DataFrame:
        """批量獲取文章內容"""
        start_time = time.time()
        
        logger.info("開始批量獲取文章內容")
        logger.info(f"參數設置: num_articles={num_articles}, ai_only={ai_only}, min_keywords={min_keywords}")
        logger.info(f"待處理文章數量: {len(articles_df)}")
        
        if db_manager:
            self.set_db_manager(db_manager)
        
        articles_contents = []
        successful_count = 0
        ai_related_count = 0
        failed_count = 0
        
        try:
            for i, (_, article) in enumerate(articles_df.head(num_articles).iterrows(), 1):
                logger.info(f"處理第 {i}/{num_articles} 篇文章")
                logger.info(f"文章標題: {article['title']}")
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
                    
                    # 合併文章資訊
                    content_data.update({
                        'title': article.get('title', content_data.get('title')),
                        'link': article['link'],
                        'category': article.get('category', content_data.get('category')),
                        'source_page': article.get('source_page', 'bnext_content')
                    })
                    
                    # 存儲到資料庫
                    if self.article_repository:
                        try:
                            db_article = self._prepare_db_article(content_data)
                            self.article_repository.create(db_article)
                            logger.info(f"成功存儲文章: {content_data['title']}")
                        except Exception as db_error:
                            logger.error(f"資料庫存儲失敗: {str(db_error)}", exc_info=True)
                    
                    articles_contents.append(content_data)
                    successful_count += 1
                    ai_related_count += 1
                    
                    # 記錄進度
                    if successful_count % 5 == 0:
                        elapsed_time = time.time() - start_time
                        avg_time = elapsed_time / successful_count
                        logger.info(f"進度報告:")
                        logger.info(f"- 已處理: {i}/{num_articles}")
                        logger.info(f"- 成功數: {successful_count}")
                        logger.info(f"- AI相關: {ai_related_count}")
                        logger.info(f"- 失敗數: {failed_count}")
                        logger.info(f"- 平均處理時間: {avg_time:.2f}秒/篇")
                
                except Exception as e:
                    failed_count += 1
                    logger.error(f"處理文章時發生錯誤: {str(e)}", exc_info=True)
        
        finally:
            # 最終統計
            end_time = time.time()
            total_time = end_time - start_time
            
            logger.info("爬取任務完成")
            logger.info(f"總耗時: {total_time:.2f}秒")
            logger.info(f"處理統計:")
            logger.info(f"- 總處理文章: {num_articles}")
            logger.info(f"- 成功獲取: {successful_count}")
            logger.info(f"- AI相關文章: {ai_related_count}")
            logger.info(f"- 處理失敗: {failed_count}")
            if successful_count > 0:
                logger.info(f"- 平均處理時間: {total_time/successful_count:.2f}秒/篇")
        
        return self._process_content_to_dataframe(articles_contents)

    def _prepare_db_article(self, content_data: Dict) -> Dict:
        """準備資料庫文章格式"""
        return {
            'title': content_data['title'],
            'summary': content_data.get('summary', ''),
            'content': content_data.get('content', ''),
            'link': content_data['link'],
            'category': content_data.get('category', ''),
            'published_at': content_data.get('publish_at', ''),
            'author': content_data.get('author', ''),
            'source': 'bnext_detail',
            'tags': ', '.join(content_data.get('tags', [])) if isinstance(content_data.get('tags'), list) else ''
        }

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
            selectors = BNEXT_CONFIG.selectors['article_detail']
            
            # 提取文章內容
            header = soup.select_one(BnextUtils.build_selector(selectors[0]))
            if not header:
                logger.error(f"無法找到文章頭部: {article_url}")
                return None
            
            article_content = self._extract_article_parts(header, soup, selectors)
            article_content['source'] = article_url
            
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

    def _extract_article_parts(self, header, soup, selectors):
        """提取文章各個部分"""
        logger.debug("開始提取文章各部分內容")
        
        try:
            # 提取各個部分並記錄日誌
            title = self._extract_with_log(header, selectors, 'title', '標題')
            summary = self._extract_with_log(header, selectors, 'summary', '摘要')
            category = self._extract_with_log(header, selectors, 'category', '分類')
            publish_at = self._extract_with_log(header, selectors, 'publish_date', '發布時間')
            author = self._extract_with_log(header, selectors, 'author', '作者')
            
            # 提取標籤
            tags = self._extract_tags(header, selectors)
            logger.debug(f"提取到 {len(tags)} 個標籤")
            
            # 提取正文
            content_text = self._extract_content(soup, selectors)
            content_length = len(content_text) if content_text else 0
            logger.debug(f"提取到正文長度: {content_length} 字符")
            
            # 提取相關連結
            related_links = self._extract_related_links(soup, selectors)
            logger.debug(f"提取到 {len(related_links)} 個相關連結")
            
            # 如果沒有找到標題，嘗試使用備用方法
            if not title:
                backup_title_selectors = ['h1', 'h1.text-4xl', '.article-title', '.title']
                for selector in backup_title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        logger.debug(f"使用備用選擇器找到標題: {title}")
                        break
            
            # 如果沒有找到摘要，嘗試使用備用方法
            if not summary:
                backup_summary_selectors = ['.summary', '.article-summary', '.text-gray-500', 'div.text-xl']
                for selector in backup_summary_selectors:
                    summary_elem = soup.select_one(selector)
                    if summary_elem:
                        summary = summary_elem.get_text(strip=True)
                        logger.debug(f"使用備用選擇器找到摘要")
                        break
            
            # 如果沒有找到分類，嘗試從URL中提取
            if not category:
                url = soup.select_one('link[rel="canonical"]')
                if url and 'href' in url.attrs:
                    category_match = re.search(r'/categories/([^/]+)', url['href'])
                    if category_match:
                        category = category_match.group(1)
                        logger.debug(f"從URL中提取分類: {category}")
            
            # 確保有發布時間
            if not publish_at:
                backup_date_selectors = ['time', '.date', '.published-date', '.article-date']
                for selector in backup_date_selectors:
                    date_elem = soup.select_one(selector)
                    if date_elem:
                        publish_at = date_elem.get_text(strip=True)
                        logger.debug(f"使用備用選擇器找到發布時間: {publish_at}")
                        break
            
            # 返回提取的所有部分
            return {
                'title': title,
                'summary': summary,
                'category': category,
                'publish_at': publish_at,
                'author': author,
                'content': content_text,
                'content_length': content_length,
                'tags': tags,
                'related_articles': related_links
            }
            
        except Exception as e:
            logger.error(f"提取文章部分時發生錯誤: {str(e)}", exc_info=True)
            return {}

    def _extract_with_log(self, element, selectors, purpose, name):
        """帶有日誌的內容提取輔助方法"""
        try:
            result_elem = BnextUtils.find_element_by_purpose(element, selectors, purpose)
            result = result_elem.get_text(strip=True) if result_elem else None
            logger.debug(f"提取{name}: {result if result else '未找到'}")
            return result
        except Exception as e:
            logger.error(f"提取{name}失敗: {str(e)}")
            return None

    def _extract_tags(self, header, selectors):
        """提取文章標籤"""
        tags = []
        try:
            # 首先嘗試使用配置中的標籤容器選擇器
            tags_container = BnextUtils.find_element_by_purpose(header, selectors, 'tags_container')
            if tags_container:
                tag_elems = tags_container.select('a')
                tags = [tag.get_text(strip=True) for tag in tag_elems if tag.get_text(strip=True)]
            
            # 如果標籤容器中沒有找到標籤，嘗試在整個頁面中查找
            if not tags:
                # 嘗試標準標籤選擇器
                tag_selectors = ['.tags a', '.tag', '.article-tags a', '.keywords a', 'meta[name="keywords"]']
                for selector in tag_selectors:
                    tag_elements = []
                    if selector == 'meta[name="keywords"]':
                        meta_tag = header.select_one(selector) or header.find_parent('html').select_one(selector)
                        if meta_tag and 'content' in meta_tag.attrs:
                            keywords = meta_tag['content'].split(',')
                            tags = [kw.strip() for kw in keywords if kw.strip()]
                            break
                    else:
                        tag_elements = header.select(selector) or header.find_parent('html').select(selector)
                        if tag_elements:
                            tags = [tag.get_text(strip=True) for tag in tag_elements if tag.get_text(strip=True)]
                            break
            
            logger.debug(f"找到 {len(tags)} 個標籤: {', '.join(tags[:5])}{'...' if len(tags) > 5 else ''}")
            return tags
        except Exception as e:
            logger.error(f"提取標籤失敗: {str(e)}")
            return []

    def _extract_content(self, soup, selectors):
        """提取文章正文內容"""
        try:
            # 嘗試使用配置中的內容選擇器
            content_elem = BnextUtils.find_element_by_purpose(soup, selectors, 'content')
            
            # 如果找不到內容元素，嘗試使用備用選擇器
            if not content_elem:
                backup_content_selectors = [
                    'div.htmlview.article-content',
                    'article .article-content', 
                    '.article-body', 
                    '.article-content',
                    '#article-content',
                    '.post-content',
                    'article',
                    'div[itemprop="articleBody"]'
                ]
                
                for selector in backup_content_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        logger.debug(f"使用備用選擇器找到內容: {selector}")
                        break
            
            if not content_elem:
                logger.warning("無法找到文章內容元素")
                return ""
            
            # 移除不需要的元素
            for unwanted in content_elem.select('script, style, .ad, .advertisement, .social-share, iframe, .social-media, .related, aside'):
                unwanted.extract()
            
            # 組織內容
            paragraphs = []
            
            # 找出所有段落和標題
            for elem in content_elem.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'ul', 'ol']):
                text = elem.get_text(strip=True)
                if text:  # 忽略空段落
                    paragraphs.append(text)
            
            # 如果沒有找到有意義的段落，直接使用整個內容區域的文本
            if not paragraphs:
                content_text = content_elem.get_text(separator='\n', strip=True)
            else:
                content_text = '\n\n'.join(paragraphs)
            
            # 格式化整理
            content_text = re.sub(r'\n{3,}', '\n\n', content_text)  # 移除過多的換行
            
            return content_text
            
        except Exception as e:
            logger.error(f"提取內容失敗: {str(e)}")
            return ""

    def _extract_related_links(self, soup, selectors):
        """提取相關文章鏈接"""
        related_links = []
        try:
            # 嘗試使用配置中的相關連結選擇器
            related_link_elems = BnextUtils.find_elements_by_purpose(soup, selectors, 'related_links')
            
            # 如果沒有找到相關連結，嘗試備用選擇器
            if not related_link_elems:
                backup_related_selectors = [
                    '.related-article a', 
                    '.related-post a', 
                    '.more-article a',
                    '.related a',
                    'blockquote a',
                    '.recommends a'
                ]
                
                for selector in backup_related_selectors:
                    related_link_elems = soup.select(selector)
                    if related_link_elems:
                        logger.debug(f"使用備用選擇器找到相關連結: {selector}")
                        break
            
            # 處理找到的連結
            if related_link_elems:
                link_urls = set()  # 用於去重
                
                for link in related_link_elems:
                    link_url = link.get('href', '')
                    link_title = link.get_text(strip=True)
                    
                    # 確保連結是完整的
                    link_url = BnextUtils.normalize_url(link_url, BNEXT_CONFIG.base_url)
                    
                    # 確保連結有效且未重複
                    if link_url and link_title and link_url not in link_urls and '/article/' in link_url:
                        link_urls.add(link_url)
                        related_links.append({
                            'title': link_title,
                            'link': link_url
                        })
            
            return related_links
            
        except Exception as e:
            logger.error(f"提取相關連結失敗: {str(e)}")
            return []

    def _process_content_to_dataframe(self, articles_contents: List[Dict]) -> pd.DataFrame:
        """將文章內容列表轉換為DataFrame"""
        # 將文章內容保存到CSV
        contents_df = pd.DataFrame(articles_contents)
        
        # 處理相關文章列表（轉換為字符串）
        if 'related_articles' in contents_df.columns:
            contents_df['related_articles'] = contents_df['related_articles'].apply(
                lambda x: '; '.join([f"{a['title']} ({a['link']})" for a in x]) if isinstance(x, list) else ''
            )
        
        # 處理標籤列表
        if 'tags' in contents_df.columns:
            contents_df['tags'] = contents_df['tags'].apply(
                lambda x: ', '.join(x) if isinstance(x, list) else ''
            )
        
        return contents_df
