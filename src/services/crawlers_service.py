import logging
from typing import Optional, Type, Any, Dict, List, TypeVar
from datetime import datetime
from src.model.base_model import Base
from src.database.database_manager import DatabaseManager
from src.model.crawlers_schema import CrawlerSettingsCreateSchema, CrawlerSettingsUpdateSchema
from src.error.errors import ValidationError
from src.model.crawlers_model import CrawlerSettings


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

    def _get_repository(self, model_class: Type[T]):
        """取得儲存庫的上下文管理器"""
        return repository_context(self.db_manager, model_class)
    
    def insert_system_settings(self, settings_data: Dict[str, Any]) -> Optional[SystemSettings]:
        """
        插入系統設定
        
        Args:
            settings_data: 系統設定資料字典
            
        Returns:
            創建成功的系統設定實例或 None
        """
        try:
            now = datetime.now()
            settings_data.update({
                'created_at': now,
            })
            
            # 使用 Pydantic 驗證資料    
            try:
                validated_data = SystemSettingsCreateSchema.model_validate(settings_data).model_dump()
            except CustomValidationError as e:
                error_msg = f"系統設定新增資料驗證錯誤: {e}"
                logger.error(error_msg)
                raise e

            with self._get_repository(SystemSettings) as (repo, session):
                # 檢查設定是否已存在
                if not repo.exists(crawler_name=validated_data['crawler_name']):
                    # 插入新的設定
                    result = repo.create(**validated_data)
                    session.commit()
                    return result
                else:
                    error_msg = f"該爬蟲名稱已存在，請使用更新功能: {validated_data['crawler_name']}"
                    logger.warning(error_msg)
                    raise CustomValidationError(error_msg)
        except Exception as e:
            error_msg = f"插入系統設定失敗: {e}"
            logger.error(error_msg)
            raise e

    def get_all_system_settings(self, limit: Optional[int] = None, offset: Optional[int] = None, 
                                sort_by: Optional[str] = None, sort_desc: bool = False) -> List[SystemSettings]:
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
                return [sys_setting for sys_setting in sys_settings]
        except Exception as e:
            error_msg = f"獲取所有系統設定失敗: {e}"
            logger.error(error_msg)
            raise e

    def search_system_settings(self, search_terms: Dict[str, Any], limit: Optional[int] = None, 
                               offset: Optional[int] = None) -> List[SystemSettings]:
        """
        搜尋系統設定
        
        Args:
            search_terms: 搜尋條件，如 {"crawler_name": "關鍵字"}
            limit: 限制返回數量
            offset: 起始偏移    
            
        Returns:
            符合條件的系統設定列表
        """
        try:
            with self._get_repository(SystemSettings) as (_, session):
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
                return [sys_setting for sys_setting in sys_settings]
        except Exception as e:
            error_msg = f"搜尋系統設定失敗: {e}"
            logger.error(error_msg)
            raise e
    
    def get_system_settings_by_id(self, sys_settings_id: int) -> Optional[SystemSettings]:
        """
        獲取特定 ID 的系統設定
        
        Args:
            sys_settings_id: 系統設定 ID
            
        Returns:
            系統設定實例或 None
        """ 
        
        try:
            with self._get_repository(SystemSettings) as (repo, _):
                sys_settings = repo.get_by_id(sys_settings_id)

                return sys_settings
        except Exception as e:
            error_msg = f"獲取系統設定失敗，ID={sys_settings_id}: {e}"
            logger.error(error_msg)
            raise e
        
    def get_system_settings_paginated(self, page: int, per_page: int, sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """
        分頁獲取系統設定
        
        Args:
            page: 頁碼  
            per_page: 每頁設定數量
            sort_by: 排序欄位，默認None
            sort_desc: 是否降序排序，默認False
        Returns:
            items: 分頁後的設定列表
            total: 總設定數量
            page: 當前頁碼
            per_page: 每頁設定數量
            total_pages: 總頁數
        """
        with self._get_repository(SystemSettings) as (repo, _):
            return repo.get_paginated(page, per_page, sort_by, sort_desc)
        
    def update_system_settings(self, sys_settings_id: int, setting_data: Dict[str, Any]) -> Optional[SystemSettings]:
        """
        更新系統設定
        
        Args:
            sys_settings_id: 系統設定 ID
            setting_data: 要更新的系統設定資料
            
        Returns:
            更新後的系統設定字典或 None
        """   
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
                except CustomValidationError as e:
                    error_msg = f"系統設定更新資料驗證失敗: {str(e)}"
                    logger.error(error_msg)
                    raise CustomValidationError(error_msg, e)

                result = repo.update(sys_setting, **validated_data)
                if not result:
                    logger.warning(f"系統設定更新失敗")
                    return None
                
                session.commit()
                return result
        except Exception as e:
            error_msg = f"更新系統設定失敗，ID={sys_settings_id}: {e}"
            logger.error(error_msg)
            raise e
    
    def batch_update_system_settings(self, sys_settings_ids: List[int], setting_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        批量更新系統設定
        
        Args:
            sys_settings_ids: 系統設定 ID 列表
            setting_data: 要更新的系統設定資料
            
        Returns:
             成功更新數量和失敗數量的字典
                success_count: 成功更新數量
                fail_count: 失敗數量
                updated_articles: 成功更新的文章列表
                missing_ids: 未找到的文章ID列表
        """
        try:
            # 自動更新 updated_at 欄位
            setting_data['updated_at'] = datetime.now()

            # 先驗證更新資料
            try:
                validated_data = SystemSettingsUpdateSchema.model_validate(setting_data).model_dump(exclude_unset=True)
            except Exception as e:
                logger.error(f"系統設定更新資料驗證失敗: {e}")
                raise e
            
            with self._get_repository(SystemSettings) as (repo, session):
                # 批量查詢所有設定
                sys_settings_to_update = session.query(SystemSettings).filter(SystemSettings.id.in_(sys_settings_ids)).all()

                # 追蹤找到的設定ID
                found_ids = [sys_setting.id for sys_setting in sys_settings_to_update]

                # 計算未找到的設定ID
                missing_ids = [id for id in sys_settings_ids if id not in found_ids]

                updated_settings = []
                # 更新找到的設定
                for sys_setting in sys_settings_to_update:
                    # 獲取當前設定資料
                    current_settings_data = {
                        "crawler_name": sys_setting.crawler_name,
                        "crawl_interval": sys_setting.crawl_interval,
                        "is_active": sys_setting.is_active
                    }

                    # 更新資料
                    current_settings_data.update(validated_data)

                    # 更新設定
                    for key, value in current_settings_data.items():
                        if hasattr(sys_setting, key):
                            setattr(sys_setting, key, value)
                    updated_settings.append(sys_setting)
                    
                # 提交更新
                session.commit()
                success_count = len(updated_settings)
                fail_count = len(missing_ids)

                logger.info(f"批量更新系統設定完成: 成功 {success_count}, 失敗 {fail_count}")
                return {
                    "success_count": success_count,
                    "fail_count": fail_count,
                    "updated_settings": updated_settings,
                    "missing_ids": missing_ids
                }
        except Exception as e:
            error_msg = f"批量更新系統設定失敗: {e}"
            logger.error(error_msg)
            raise e

    def delete_system_settings(self, sys_settings_id: int) -> bool:
        """
        刪除系統設定
        
        Args:
            sys_settings_id: 系統設定 ID
            
        Returns:
            是否成功刪除
        """
        try:
            with self._get_repository(SystemSettings) as (_, session):
                 # 直接執行刪除操作並返回受影響的行數
                result = session.query(SystemSettings).filter(SystemSettings.id == sys_settings_id).delete()
                
                if result == 0:
                    logger.warning(f"欲刪除的設定不存在，ID={sys_settings_id}")
                    return False
                
                session.commit()
                logger.info(f"成功刪除系統設定，ID={sys_settings_id}")
                return True
        except Exception as e:
            error_msg = f"刪除系統設定失敗，ID={sys_settings_id}: {e}"
            logger.error(error_msg)
            raise e
        
        
    def batch_delete_system_settings(self, sys_settings_ids: List[int]) -> Dict[str, Any]:
        """
        批量刪除系統設定
        
        Args:
            sys_settings_ids: 系統設定 ID 列表
            
        Returns:
                成功刪除數量和失敗數量的字典
                success_count: 成功刪除數量
                fail_count: 失敗數量
                missing_ids: 未找到的文章ID列表
        """
        if not sys_settings_ids:
            return {
                "success_count": 0,
                "fail_count": 0,
                "missing_ids": []
            } 

        try:
            with self._get_repository(SystemSettings) as (repo, session):
                # 先查詢所有需要刪除的設定
                sys_settings_to_delete = session.query(SystemSettings).filter(SystemSettings.id.in_(sys_settings_ids)).all()
                
                # 追蹤找到的設定ID
                found_ids = [sys_setting.id for sys_setting in sys_settings_to_delete]
                
                # 計算未找到的設定ID
                missing_ids = list(set(sys_settings_ids) - set(found_ids))
                
                # 刪除找到的設定
                if sys_settings_to_delete:
                    # 使用bulk_delete操作而非逐個刪除
                    for sys_setting in sys_settings_to_delete:
                        session.delete(sys_setting)
                        
                    session.commit()
                
                success_count = len(found_ids)
                fail_count = len(missing_ids)
                
                logger.info(f"批量刪除系統設定完成: 成功 {success_count}, 失敗 {fail_count}")
                
                return {
                    "success_count": success_count,
                    "fail_count": fail_count,
                    "missing_ids": missing_ids
                }
        except Exception as e:
            error_msg = f"批量刪除系統設定失敗: {e}"        
            logger.error(error_msg)
            session.rollback()
            raise  
    
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
