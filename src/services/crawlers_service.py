import logging
from typing import Optional, Dict, Any, List, TypeVar, Tuple, Type, cast
from src.models.crawlers_model import Base, Crawlers
from datetime import datetime, timezone
from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema
from src.error.errors import DatabaseOperationError, ValidationError
from src.database.crawlers_repository import CrawlersRepository
from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通用類型變數，用於泛型方法
T = TypeVar('T', bound=Base)

# 添加 DatetimeProvider 輔助類，用於在測試中替換
class DatetimeProvider:
    @staticmethod
    def now(tz=None):
        return datetime.now(tz)

class CrawlersService(BaseService[Crawlers]):
    """爬蟲服務，提供爬蟲相關業務邏輯"""
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self.datetime_provider = DatetimeProvider()

    def _get_repository_mapping(self) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {
            'Crawler': (CrawlersRepository, Crawlers)
        }
    
    def _get_repository(self) -> CrawlersRepository:
        """獲取爬蟲資料庫訪問對象"""
        return cast(CrawlersRepository, super()._get_repository('Crawler'))

    def create_crawler(self, crawler_data: Dict[str, Any]) -> Dict[str, Any]:
        """創建新爬蟲設定"""
        try:
            with self._transaction():
                # 添加必要的欄位
                now = self.datetime_provider.now(timezone.utc)
                crawler_data.update({
                    'created_at': now,
                    'updated_at': now
                })
                
                # 使用 Pydantic 驗證資料
                try:
                    validated_data = CrawlersCreateSchema.model_validate(crawler_data).model_dump()
                except Exception as e:
                    return {
                        'success': False,
                        'message': f"爬蟲設定資料驗證失敗: {str(e)}"
                    }

                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawler': None
                    }
                result = crawler_repo.create(validated_data)
                
                if not result:
                    return {
                        'success': False,
                        'message': "創建爬蟲設定失敗",
                        'crawler': None
                    }
                
                return {
                    'success': True,
                    'message': "爬蟲設定創建成功",
                    'crawler': result
                }
                
        except Exception as e:
            logger.error(f"創建爬蟲設定失敗: {str(e)}")
            raise e

    def get_all_crawlers(self, limit: Optional[int] = None, offset: Optional[int] = None,
                        sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """獲取所有爬蟲設定"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawlers': []
                    }
                crawlers = crawler_repo.get_all(
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc
                )
                
                return {
                    'success': True,
                    'message': "獲取爬蟲設定列表成功",
                    'crawlers': crawlers or []
                }
        except Exception as e:
            logger.error(f"獲取所有爬蟲設定失敗: {str(e)}")
            raise e

    def get_crawler_by_id(self, crawler_id: int) -> Dict[str, Any]:
        """根據ID獲取爬蟲設定"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawler': None
                    }
                crawler = crawler_repo.get_by_id(crawler_id)
                
                if not crawler:
                    return {
                        'success': False,
                        'message': f"爬蟲設定不存在，ID={crawler_id}",
                        'crawler': None
                    }
                
                return {
                    'success': True,
                    'message': "獲取爬蟲設定成功",
                    'crawler': crawler
                }
        except Exception as e:
            logger.error(f"獲取爬蟲設定失敗，ID={crawler_id}: {str(e)}")
            raise e

    def update_crawler(self, crawler_id: int, crawler_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新爬蟲設定"""
        try:
            with self._transaction():
                # 自動更新 updated_at 欄位
                crawler_data['updated_at'] = self.datetime_provider.now(timezone.utc)
                
                # 使用 Pydantic 驗證資料
                try:
                    validated_data = CrawlersUpdateSchema.model_validate(crawler_data).model_dump()
                except Exception as e:
                    return {
                        'success': False,
                        'message': f"爬蟲設定更新資料驗證失敗: {str(e)}",
                        'crawler': None
                    }
                
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawler': None
                    }
                
                # 檢查爬蟲是否存在
                original_crawler = crawler_repo.get_by_id(crawler_id)
                if not original_crawler:
                    return {
                        'success': False,
                        'message': f"爬蟲設定不存在，ID={crawler_id}",
                        'crawler': None
                    }
                
                result = crawler_repo.update(crawler_id, validated_data)
                
                if not result:
                    return {
                        'success': False,
                        'message': f"更新爬蟲設定失敗，ID={crawler_id}",
                        'crawler': None
                    }
                
                return {
                    'success': True,
                    'message': "爬蟲設定更新成功",
                    'crawler': result
                }
                
        except Exception as e:
            logger.error(f"更新爬蟲設定失敗，ID={crawler_id}: {str(e)}")
            raise e

    def delete_crawler(self, crawler_id: int) -> Dict[str, Any]:
        """刪除爬蟲設定"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                    }
                result = crawler_repo.delete(crawler_id)
                
                if not result:
                    return {
                        'success': False,
                        'message': f"爬蟲設定不存在，ID={crawler_id}"
                    }
                
                return {
                    'success': True,
                    'message': "爬蟲設定刪除成功"
                }
                
        except Exception as e:
            logger.error(f"刪除爬蟲設定失敗，ID={crawler_id}: {str(e)}")
            raise e

    def get_active_crawlers(self) -> Dict[str, Any]:
        """獲取所有活動中的爬蟲設定"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawlers': []
                    }
                crawlers = crawler_repo.find_active_crawlers()
                if not crawlers:
                    return {
                        'success': False,
                        'message': "找不到任何活動中的爬蟲設定",
                        'crawlers': []
                    }
                return {
                    'success': True,
                    'message': "獲取活動中的爬蟲設定成功",
                    'crawlers': crawlers or []
                }
        except Exception as e:
            logger.error(f"獲取活動中的爬蟲設定失敗: {str(e)}")
            raise e

    def toggle_crawler_status(self, crawler_id: int) -> Dict[str, Any]:
        """切換爬蟲活躍狀態"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawler': None
                    }
                result = crawler_repo.toggle_active_status(crawler_id)
                
                if not result:
                    return {
                        'success': False,
                        'message': f"爬蟲設定不存在或切換失敗，ID={crawler_id}",
                        'crawler': None
                    }
                
                updated_crawler = crawler_repo.get_by_id(crawler_id)
                if updated_crawler: 
                    return {
                        'success': True,
                        'message': f"成功切換爬蟲狀態，新狀態={updated_crawler.is_active}",
                        'crawler': updated_crawler
                    }
                else:
                    return {
                        'success': False,
                        'message': f"爬蟲設定不存在，ID={crawler_id}",
                        'crawler': None
                    }
                
        except Exception as e:
            logger.error(f"切換爬蟲狀態失敗，ID={crawler_id}: {str(e)}")
            raise e
    
    def get_crawlers_by_name(self, name: str) -> Dict[str, Any]:
        """根據名稱模糊查詢爬蟲設定"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawlers': []
                    }
                crawlers = crawler_repo.find_by_crawler_name(name)
                if not crawlers:
                    return {
                        'success': False,
                        'message': "找不到任何符合條件的爬蟲設定",
                        'crawlers': []
                    }
                return {
                    'success': True,
                    'message': "獲取爬蟲設定列表成功",
                    'crawlers': crawlers or []
                }   
        except Exception as e:
            logger.error(f"獲取爬蟲設定列表失敗: {str(e)}")
            raise e
    
    def get_crawlers_by_type(self, crawler_type: str) -> Dict[str, Any]:
        """根據爬蟲類型查找爬蟲"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawlers': []
                    }
                crawlers = crawler_repo.find_by_type(crawler_type)
                if not crawlers:
                    return {
                        'success': False,
                        'message': f"找不到類型為 {crawler_type} 的爬蟲設定",
                        'crawlers': []
                    }
                return {
                    'success': True,
                    'message': f"獲取類型為 {crawler_type} 的爬蟲設定列表成功",
                    'crawlers': crawlers
                }
        except Exception as e:
            logger.error(f"獲取類型為 {crawler_type} 的爬蟲設定列表失敗: {str(e)}")
            raise e
    
    def get_crawlers_by_target(self, target_pattern: str) -> Dict[str, Any]:
        """根據爬取目標模糊查詢爬蟲"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawlers': []
                    }
                crawlers = crawler_repo.find_by_target(target_pattern)
                if not crawlers:
                    return {
                        'success': False,
                        'message': f"找不到目標包含 {target_pattern} 的爬蟲設定",
                        'crawlers': []
                    }
                return {
                    'success': True,
                    'message': f"獲取目標包含 {target_pattern} 的爬蟲設定列表成功",
                    'crawlers': crawlers
                }
        except Exception as e:
            logger.error(f"獲取目標包含 {target_pattern} 的爬蟲設定列表失敗: {str(e)}")
            raise e
    
    def get_crawler_statistics(self) -> Dict[str, Any]:
        """獲取爬蟲統計信息"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'statistics': None
                    }
                statistics = crawler_repo.get_crawler_statistics()
                return {
                    'success': True,
                    'message': "獲取爬蟲統計信息成功",
                    'statistics': statistics
                }
        except Exception as e:
            logger.error(f"獲取爬蟲統計信息失敗: {str(e)}")
            raise e
    
    def get_crawler_by_exact_name(self, crawler_name: str) -> Dict[str, Any]:
        """根據爬蟲名稱精確查詢"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawler': None
                    }
                crawler = crawler_repo.find_by_crawler_name_exact(crawler_name)
                if not crawler:
                    return {
                        'success': False,
                        'message': f"找不到名稱為 {crawler_name} 的爬蟲設定",
                        'crawler': None
                    }
                return {
                    'success': True,
                    'message': "獲取爬蟲設定成功",
                    'crawler': crawler
                }
        except Exception as e:
            logger.error(f"獲取名稱為 {crawler_name} 的爬蟲設定失敗: {str(e)}")
            raise e
    
    def create_or_update_crawler(self, crawler_data: Dict[str, Any]) -> Dict[str, Any]:
        """創建或更新爬蟲設定
        
        如果提供 ID 則更新現有爬蟲，否則創建新爬蟲
        """
        try:
            with self._transaction():
                # 添加時間戳
                now = self.datetime_provider.now(timezone.utc)
                crawler_copy = crawler_data.copy()  # 複製資料，避免直接修改原始資料
                
                logger.info(f"開始處理 create_or_update_crawler: {crawler_copy}")
                
                # 確保資料中有建立或更新時間欄位
                if 'id' not in crawler_copy or not crawler_copy['id']:
                    # 創建時添加 created_at
                    crawler_copy['created_at'] = now
                
                # 更新時間總是添加
                crawler_copy['updated_at'] = now
                
                # 驗證資料
                try:
                    is_update = 'id' in crawler_copy and crawler_copy['id']
                    logger.info(f"操作類型: {'更新' if is_update else '創建'}")
                    
                    if is_update:
                        # 驗證 ID 是否存在
                        crawler_repo = self._get_repository()
                        if not crawler_repo:
                            logger.error("無法取得資料庫存取器")
                            return {
                                'success': False,
                                'message': '無法取得資料庫存取器',
                                'crawler': None
                            }
                        
                        logger.info(f"正在檢查爬蟲 ID: {crawler_copy['id']}")
                        existing_crawler = crawler_repo.get_by_id(crawler_copy['id'])
                        if not existing_crawler:
                            logger.error(f"爬蟲設定不存在，ID={crawler_copy['id']}")
                            return {
                                'success': False,
                                'message': f"爬蟲設定不存在，ID={crawler_copy['id']}",
                                'crawler': None
                            }
                        
                        # 更新模式：使用 update 方法直接更新，因為 create_or_update 移除 ID 後可能導致問題
                        crawler_id = crawler_copy.pop('id')
                        logger.info(f"準備更新爬蟲，ID={crawler_id}，資料: {crawler_copy}")
                        
                        try:
                            validated_data = CrawlersUpdateSchema.model_validate(crawler_copy).model_dump()
                            logger.info(f"已驗證的更新資料: {validated_data}")
                        except Exception as validation_error:
                            logger.error(f"更新資料驗證失敗: {validation_error}")
                            return {
                                'success': False,
                                'message': f"爬蟲設定更新資料驗證失敗: {str(validation_error)}",
                                'crawler': None
                            }
                        
                        try:
                            result = crawler_repo.update(crawler_id, validated_data)
                            logger.info(f"更新結果: {result}")
                        except Exception as update_error:
                            logger.error(f"更新操作執行失敗: {update_error}")
                            return {
                                'success': False,
                                'message': f"爬蟲設定更新操作失敗: {str(update_error)}",
                                'crawler': None
                            }
                        
                        operation = "更新"
                    else:
                        # 創建模式：使用 create 方法
                        logger.info(f"準備創建爬蟲，資料: {crawler_copy}")
                        
                        try:
                            validated_data = CrawlersCreateSchema.model_validate(crawler_copy).model_dump()
                            logger.info(f"已驗證的創建資料: {validated_data}")
                        except Exception as validation_error:
                            logger.error(f"創建資料驗證失敗: {validation_error}")
                            return {
                                'success': False,
                                'message': f"爬蟲設定創建資料驗證失敗: {str(validation_error)}",
                                'crawler': None
                            }
                        
                        crawler_repo = self._get_repository()
                        if not crawler_repo:
                            logger.error("無法取得資料庫存取器")
                            return {
                                'success': False,
                                'message': '無法取得資料庫存取器',
                                'crawler': None
                            }
                            
                        try:
                            result = crawler_repo.create(validated_data)
                            logger.info(f"創建結果: {result}")
                        except Exception as create_error:
                            logger.error(f"創建操作執行失敗: {create_error}")
                            return {
                                'success': False,
                                'message': f"爬蟲設定創建操作失敗: {str(create_error)}",
                                'crawler': None
                            }
                            
                        operation = "創建"
                        
                except Exception as e:
                    logger.error(f"處理過程中發生未預期錯誤: {e}")
                    return {
                        'success': False,
                        'message': f"爬蟲設定資料驗證失敗: {str(e)}",
                        'crawler': None
                    }
                
                if not result:
                    logger.error(f"爬蟲設定{operation}失敗，未返回結果")
                    return {
                        'success': False,
                        'message': f"爬蟲設定{operation}失敗",
                        'crawler': None
                    }
                
                logger.info(f"爬蟲設定{operation}成功: {result}")
                return {
                    'success': True,
                    'message': f"爬蟲設定{operation}成功",
                    'crawler': result
                }
        except Exception as e:
            logger.error(f"創建或更新爬蟲設定失敗: {str(e)}")
            return {
                'success': False,
                'message': f"創建或更新爬蟲設定時發生錯誤: {str(e)}",
                'crawler': None
            }
    
    def batch_toggle_crawler_status(self, crawler_ids: List[int], active_status: bool) -> Dict[str, Any]:
        """批量設置爬蟲的活躍狀態"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'result': None
                    }
                
                result = crawler_repo.batch_toggle_active(crawler_ids, active_status)
                
                action = "啟用" if active_status else "停用"
                if result['success_count'] > 0:
                    return {
                        'success': True,
                        'message': f"批量{action}爬蟲設定完成，成功: {result['success_count']}，失敗: {result['fail_count']}",
                        'result': result
                    }
                else:
                    return {
                        'success': False,
                        'message': f"批量{action}爬蟲設定失敗，所有操作均未成功",
                        'result': result
                    }
        except Exception as e:
            logger.error(f"批量切換爬蟲狀態失敗: {str(e)}")
            raise e
    
    def get_filtered_crawlers(self, 
                              filter_dict: Dict[str, Any], 
                              page: int = 1, 
                              per_page: int = 10,
                              sort_by: Optional[str] = None, 
                              sort_desc: bool = False) -> Dict[str, Any]:
        """根據過濾條件獲取分頁爬蟲列表"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'data': None
                    }
                
                result = crawler_repo.get_paginated_by_filter(
                    filter_dict=filter_dict,
                    page=page,
                    per_page=per_page,
                    sort_by=sort_by,
                    sort_desc=sort_desc
                )
                
                if not result or not result.get('items'):
                    return {
                        'success': False,
                        'message': "找不到符合條件的爬蟲設定",
                        'data': {
                            'items': [],
                            'page': page,
                            'per_page': per_page,
                            'total': 0,
                            'total_pages': 0,
                            'has_next': False,
                            'has_prev': False
                        }
                    }
                
                return {
                    'success': True,
                    'message': "獲取爬蟲設定列表成功",
                    'data': result
                }
        except Exception as e:
            logger.error(f"獲取過濾後的爬蟲設定列表失敗: {str(e)}")
            raise e
