import logging
from typing import Optional, Type, Any, Dict, List, Tuple, TypeVar
from datetime import datetime
from src.model.models import SystemSettings, Base
from src.model.database_manager import DatabaseManager
from src.model.repository import Repository
from contextlib import contextmanager
from pydantic import ValidationError
from .system_settings_schema import SystemSettingsCreateSchema, SystemSettingsUpdateSchema


# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通用類型變數，用於泛型方法
T = TypeVar('T', bound=Base)

class SystemSettingsService:
    """系統設定服務，提供系統設定相關業務邏輯"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    # 增加裝飾器來包裝通用的 session 與 repo 操作
    @contextmanager
    def _get_repository(self, model_class: Type[T]):
        """取得儲存庫的上下文管理器"""
        with self.db_manager.session_scope() as session:
            repo = Repository(session, model_class)
            try:
                yield repo, session
            except Exception as e:
                error_msg = f"儲存庫操作錯誤: {e}"
                logger.error(error_msg, exc_info=True)
                session.rollback()
                raise
    
    def insert_system_settings(self, settings_data: Dict[str, Any]) ->  Optional[Dict[str, Any]]:
        """
        插入系統設定
        
        Args:
            settings: 系統設定實例
            
        Returns:
            成功時返回 SystemSettings 實例，失敗時返回 None
        """
        try:
            now = datetime.now()
            settings_data.update({
                'created_at': now,
            })
            
            # 使用 Pydantic 驗證資料    
            try:
                validated_data = SystemSettingsCreateSchema.model_validate(settings_data).model_dump()
            except ValidationError as e:
                error_msg = f"資料驗證錯誤: {e}"
                logger.error(error_msg, exc_info=True)
                return None

            with self._get_repository(SystemSettings) as (repo, session):
                # 檢查設定是否已存在
                if not repo.exists(crawler_name=validated_data['crawler_name']):
                    # 插入新的設定
                    sys_settings = repo.create(**validated_data)
                    session.commit()
                    
                    # 直接返回字典
                    return {
                        "id": sys_settings.id,
                        "crawler_name": sys_settings.crawler_name,
                        "crawl_interval": sys_settings.crawl_interval,
                        "is_active": sys_settings.is_active,
                        "created_at": sys_settings.created_at,
                        "updated_at": sys_settings.updated_at,
                        "last_crawl_time": sys_settings.last_crawl_time
                    }
                else:
                    error_msg = f"設定已存在: {validated_data['crawler_name']}"
                    logger.warning(error_msg)
                    return None
        except Exception as e:
            error_msg = f"插入系統設定失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return None

    def get_all_system_settings(self, limit: Optional[int] = None, offset: Optional[int] = None, sort_by: Optional[str] = None, sort_desc: bool = False) -> List[Dict[str, Any]]:
        """
        獲取所有系統設定，支持分頁和排序
        
        Args:
            limit: 限制返回數量，預設為 None（返回全部）
            offset: 起始偏移，預設為 None
            sort_by: 排序欄位，預設為 None
            sort_desc: 是否降序排序，預設為 False
            
        Returns:
            所有系統設定列表
        """
        try:
            with self._get_repository(SystemSettings) as (repo, _):
                # 獲取所有設定
                sys_settings = repo.get_all(limit=limit, offset=offset, sort_by=sort_by, sort_desc=sort_desc)
                # 使用列表推導式簡化轉換過程，並確保返回類型為 List[Dict[str, Any]]
                return [sys_setting_dict for sys_setting in sys_settings
                        if (sys_setting_dict := self._sys_settings_to_dict(sys_setting)) is not None]
        except Exception as e:
            error_msg = f"獲取所有系統設定失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return []

    def search_system_settings(self, search_terms: Dict[str, Any], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        搜尋系統設定
        
        Args:
            search_terms: 搜尋條件，如 {"crawler_name": "關鍵字"}
            limit: 限制返回數量
            offset: 起始偏移    
            
        Returns:
            符合條件的系統設定字典列表
        """
        try:
            with self._get_repository(SystemSettings) as (repo, session):
                # 建立查詢
                query = session.query(SystemSettings)
                
                # 應用搜尋條件
                if "crawler_name" in search_terms and search_terms["crawler_name"]:
                    query = query.filter(SystemSettings.crawler_name.like(f"%{search_terms['crawler_name']}%"))
                
                if "is_active" in search_terms and search_terms["is_active"] is not None:
                    query = query.filter(SystemSettings.is_active == search_terms["is_active"])
                    
                # 應用分頁
                if limit is not None:
                    query = query.limit(limit)
                if offset is not None:
                    query = query.offset(offset)
                    
                # 執行查詢
                sys_settings = query.all()
                return [sys_settings_dict for sys_setting in sys_settings
                        if (sys_settings_dict := self._sys_settings_to_dict(sys_setting)) is not None]
        except Exception as e:
            error_msg = f"搜尋系統設定失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return []
    
    def get_system_settings_by_id(self, sys_settings_id: int) -> Optional[Dict[str, Any]]:
        """
        獲取特定 ID 的系統設定
        
        Args:
            sys_settings_id: 系統設定 ID
            
        Returns:
            系統設定字典或 None
        """ 
        if not isinstance(sys_settings_id, int) or sys_settings_id <= 0:
            logger.error(f"無效的系統設定ID: {sys_settings_id}")
            return None
        
        try:
            with self._get_repository(SystemSettings) as (repo, _):
                sys_settings = repo.get_by_id(sys_settings_id)
                return self._sys_settings_to_dict(sys_settings) if sys_settings else None
        except Exception as e:
            error_msg = f"獲取系統設定失敗，ID={sys_settings_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return None
        
    def get_system_settings_paginated(self, page: int, per_page: int, sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """
        獲取分頁的系統設定
        
        Args:
            page: 頁碼
            per_page: 每頁設定數量
            sort_by: 排序欄位，預設None
            sort_desc: 是否降序排序，預設False
            
        Returns:
            分頁後的系統設定字典列表
        """
        try:
            with self._get_repository(SystemSettings) as (repo, _):
                # 計算總設定數量
                total_settings = len(repo.get_all())
                
                # 計算總頁數
                total_pages = (total_settings + per_page - 1) // per_page
                
                # 計算起始偏移
                offset = (page - 1) * per_page
                
                # 獲取分頁後的設定
                sys_settings = repo.get_all(limit=per_page, offset=offset, sort_by=sort_by, sort_desc=sort_desc)    
                
                return {
                    "items": [self._sys_settings_to_dict(sys_setting) for sys_setting in sys_settings],
                    "total": total_settings,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": total_pages
                }   
        except Exception as e:
            error_msg = f"分頁獲取系統設定失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return {
                "items": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0
            }   
        
    def update_system_settings(self, sys_settings_id: int, setting_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        更新系統設定
        
        Args:
            sys_settings_id: 系統設定 ID
            setting_data: 要更新的系統設定資料
            
        Returns:
            更新後的系統設定字典或 None
        """
        # 移除可能意外傳入的 created_at
        setting_data.pop('created_at', None)
        
        # 驗證輸入
        if not isinstance(sys_settings_id, int) or sys_settings_id <= 0:
            logger.error(f"無效的系統設定ID: {sys_settings_id}")
            return None
        
        if not setting_data:
            logger.error("更新資料為空")
            return None
        
        try:
            # 自動更新 updated_at 欄位
            setting_data['updated_at'] = datetime.now()
            
            with self._get_repository(SystemSettings) as (repo, session):
                sys_setting = repo.get_by_id(sys_settings_id)  

                if not sys_setting:
                    logger.warning(f"欲更新的設定不存在，ID={sys_settings_id}") 
                    return None
                
                # 獲取當前設定資料
                current_settings_data = {
                    "crawler_name": sys_setting.crawler_name,
                    "crawl_interval": sys_setting.crawl_interval,
                    "is_active": sys_setting.is_active
                }
                
                # 更新資料
                current_settings_data.update(setting_data)
                
                # 使用 Pydantic 驗證資料
                try:
                    validated_data = SystemSettingsUpdateSchema.model_validate(current_settings_data).model_dump()
                except ValidationError as e:
                    error_msg = f"資料驗證錯誤: {e}"
                    logger.error(error_msg, exc_info=True)
                    return None

                sys_setting = repo.update(sys_setting, **validated_data)
                session.commit()
                return self._sys_settings_to_dict(sys_setting)
        except Exception as e:
            error_msg = f"更新系統設定失敗，ID={sys_settings_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return None
    
    def batch_update_system_settings(self, sys_settings_ids: List[int], setting_data: Dict[str, Any]) -> Tuple[int, int]:
        """
        批量更新系統設定
        
        Args:
            sys_settings_ids: 系統設定 ID 列表
            setting_data: 要更新的系統設定資料
            
        Returns:
            成功更新數量和失敗數量的元組
        """
        success_count = 0
        fail_count = 0
        
        for sys_settings_id in sys_settings_ids:
            result = self.update_system_settings(sys_settings_id, setting_data)
            if result:
                success_count += 1
            else:
                fail_count += 1
                
        logger.info(f"批量更新系統設定完成: 成功 {success_count}, 失敗 {fail_count}")
        return (success_count, fail_count)

    def delete_system_settings(self, sys_settings_id: int) -> bool:
        """
        刪除系統設定
        
        Args:
            sys_settings_id: 系統設定 ID
            
        Returns:
            是否成功刪除
        """
        if not isinstance(sys_settings_id, int) or sys_settings_id <= 0:
            logger.error(f"無效的系統設定ID: {sys_settings_id}")
            return False
        
        try:
            with self._get_repository(SystemSettings) as (repo, session):
                sys_setting = repo.get_by_id(sys_settings_id)
                
                if not sys_setting:
                    logger.warning(f"欲刪除的設定不存在，ID={sys_settings_id}")
                    return False
                
                repo.delete(sys_setting)
                session.commit()
                logger.info(f"成功刪除系統設定，ID={sys_settings_id}")
                return True
        except Exception as e:
            error_msg = f"刪除系統設定失敗，ID={sys_settings_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return False
        
        
    def batch_delete_system_settings(self, sys_settings_ids: List[int]) -> Tuple[int, int]:
        """
        批量刪除系統設定
        
        Args:
            sys_settings_ids: 系統設定 ID 列表
            
        Returns:
            成功刪除數量和失敗數量的元組
        """
        success_count = 0
        fail_count = 0  

        for sys_settings_id in sys_settings_ids:
            result = self.delete_system_settings(sys_settings_id)
            if result:
                success_count += 1
            else:
                fail_count += 1
                
        logger.info(f"批量刪除系統設定完成: 成功 {success_count}, 失敗 {fail_count}")
        return (success_count, fail_count)
    
    def _sys_settings_to_dict(self, sys_settings) -> Optional[Dict[str, Any]]:
        """
        將 SystemSettings 實例轉換為字典
        
        Args:
            sys_settings: SystemSettings 實例或字典
            
        Returns:
            系統設定字典或 None
        """
        if not sys_settings:
            return None
        
        try:
            # 如果已經是字典，直接返回
            if isinstance(sys_settings, dict):
                return sys_settings
            
            return {
                "id": sys_settings.id,
                "crawler_name": sys_settings.crawler_name,
                "crawl_interval": sys_settings.crawl_interval,
                "is_active": sys_settings.is_active,
                "created_at": sys_settings.created_at,
                "updated_at": sys_settings.updated_at,
                "last_crawl_time": sys_settings.last_crawl_time
            }
        except Exception as e:
            try:
                sys_settings_id = getattr(sys_settings, 'id', 'N/A')
                error_msg = f"轉換系統設定字典失敗，ID={sys_settings_id}: {e}"
                logger.error(error_msg, exc_info=True)
                return None
            except Exception as e:
                error_msg = f"轉換系統設定字典失敗: {e}"
                logger.error(error_msg, exc_info=True)
                return None 