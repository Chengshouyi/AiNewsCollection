from .base_repository import BaseRepository, SchemaType
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_task_history_schema import CrawlerTaskHistoryCreateSchema, CrawlerTaskHistoryUpdateSchema
from typing import List, Optional, Dict, Any, Type
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import logging
from src.error.errors import ValidationError, DatabaseOperationError
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerTaskHistoryRepository(BaseRepository['CrawlerTaskHistory']):
    """CrawlerTaskHistory 特定的Repository"""
    
    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """獲取對應的schema類別"""
        if schema_type == SchemaType.UPDATE:
            return CrawlerTaskHistoryUpdateSchema
        elif schema_type == SchemaType.CREATE:
            return CrawlerTaskHistoryCreateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")
    
    def create(self, entity_data: Dict[str, Any]) -> Optional[CrawlerTaskHistory]:
        """
        創建爬蟲任務歷史記錄，先進行 Pydantic 驗證，然後調用內部創建。
        
        Args:
            entity_data: 實體資料
            
        Returns:
            創建的爬蟲任務歷史實體
        """
        try:
            # 1. 設定特定預設值
            copied_data = entity_data.copy()
            if 'start_time' not in copied_data:
                copied_data['start_time'] = datetime.now(timezone.utc)
            if 'success' not in copied_data:
                copied_data['success'] = False
            if 'articles_count' not in copied_data:
                copied_data['articles_count'] = 0
            
            # 2. 執行 Pydantic 驗證
            validated_data = self.validate_data(copied_data, SchemaType.CREATE)
            
            # 3. 將已驗證的資料傳給內部方法
            return self._create_internal(validated_data)
        except ValidationError as e:
            logger.error(f"創建 CrawlerTaskHistory 驗證失敗: {e}")
            raise # 重新拋出讓 Service 層處理
        except DatabaseOperationError: # 捕捉來自 _create_internal 的錯誤
            raise # 重新拋出
        except Exception as e: # 捕捉其他意外錯誤
            logger.error(f"創建 CrawlerTaskHistory 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"創建 CrawlerTaskHistory 時發生未預期錯誤: {e}") from e
    
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[CrawlerTaskHistory]:
        """
        更新爬蟲任務歷史記錄，先進行 Pydantic 驗證，然後調用內部更新。
        
        Args:
            entity_id: 實體ID
            entity_data: 要更新的實體資料
            
        Returns:
            更新後的爬蟲任務歷史實體，如果實體不存在則返回None
        """
        try:
            # 1. 檢查實體是否存在
            existing_entity = self.get_by_id(entity_id)
            if not existing_entity:
                logger.warning(f"更新爬蟲任務歷史記錄失敗，ID不存在: {entity_id}")
                return None
            
            # 如果更新資料為空，直接返回已存在的實體
            if not entity_data:
                return existing_entity
                
            # 2. 檢查不可更新的欄位
            copied_data = entity_data.copy()
            immutable_fields = ['id', 'task_id', 'start_time', 'created_at']
            for field in immutable_fields:
                if field in copied_data:
                    logger.warning(f"嘗試更新不可修改的欄位: {field}，該欄位將被忽略")
                    copied_data.pop(field)
            
            # 如果剩餘更新資料為空，直接返回已存在的實體
            if not copied_data:
                return existing_entity
                
            # 3. 執行 Pydantic 驗證 (獲取 update payload)
            update_payload = self.validate_data(copied_data, SchemaType.UPDATE)
            
            # 4. 將已驗證的 payload 傳給內部方法
            return self._update_internal(entity_id, update_payload)
        except ValidationError as e:
            logger.error(f"更新 CrawlerTaskHistory (ID={entity_id}) 驗證失敗: {e}")
            raise # 重新拋出
        except DatabaseOperationError: # 捕捉來自 _update_internal 的錯誤
            raise # 重新拋出
        except Exception as e: # 捕捉其他意外錯誤
            logger.error(f"更新 CrawlerTaskHistory (ID={entity_id}) 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"更新 CrawlerTaskHistory (ID={entity_id}) 時發生未預期錯誤: {e}") from e

    def find_by_task_id(self, task_id: int) -> List['CrawlerTaskHistory']:
        """根據任務ID查詢相關的歷史記錄"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(
                task_id=task_id
            ).all(),
            err_msg=f"查詢任務ID為{task_id}的歷史記錄時發生錯誤"
        )
    
    def find_successful_histories(self) -> List['CrawlerTaskHistory']:
        """查詢所有成功的任務歷史記錄"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(
                success=True
            ).all(),
            err_msg="查詢成功任務歷史記錄時發生錯誤"
        )
    
    def find_failed_histories(self) -> List['CrawlerTaskHistory']:
        """查詢所有失敗的任務歷史記錄"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(
                success=False
            ).all(),
            err_msg="查詢失敗任務歷史記錄時發生錯誤"
        )
    
    def find_histories_with_articles(self, min_articles: int = 1) -> List['CrawlerTaskHistory']:
        """查詢文章數量大於指定值的歷史記錄"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.articles_count >= min_articles
            ).all(),
            err_msg=f"查詢文章數量大於{min_articles}的歷史記錄時發生錯誤"
        )
    
    def find_histories_by_date_range(
        self, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None
    ) -> List['CrawlerTaskHistory']:
        """根據日期範圍查詢歷史記錄"""
        def query_builder():
            query = self.session.query(self.model_class)
            
            if start_date:
                query = query.filter(self.model_class.start_time >= start_date)
            
            if end_date:
                query = query.filter(self.model_class.start_time <= end_date)
            
            return query.all()
            
        return self.execute_query(
            query_builder,
            err_msg="根據日期範圍查詢歷史記錄時發生錯誤"
        )
    
    def get_total_articles_count(self, task_id: Optional[int] = None) -> int:
        """
        獲取總文章數量
        
        :param task_id: 可選的任務ID，如果提供則只計算該任務的文章數
        :return: 文章總數
        """
        def query_builder():
            query = self.session.query(self.model_class)
            
            if task_id is not None:
                query = query.filter_by(task_id=task_id)
            
            return sum(int(history.articles_count or 0) for history in query.all())
            
        return self.execute_query(
            query_builder,
            err_msg="獲取總文章數量時發生錯誤"
        )
    
    def get_latest_history(self, task_id: int) -> Optional['CrawlerTaskHistory']:
        """
        獲取指定任務的最新歷史記錄
        
        :param task_id: 任務ID
        :return: 最新的歷史記錄，如果不存在則返回 None
        """
        return self.execute_query(
            lambda: (
                self.session.query(self.model_class)
                .filter_by(task_id=task_id)
                .order_by(self.model_class.start_time.desc())
                .first()
            ),
            err_msg=f"獲取任務ID為{task_id}的最新歷史記錄時發生錯誤"
        )
    
    def get_histories_older_than(self, days: int) -> List['CrawlerTaskHistory']:
        """
        獲取超過指定天數的歷史記錄
        
        :param days: 天數
        :return: 超過指定天數的歷史記錄列表
        """
        def query_builder():
            threshold_date = datetime.now() - timedelta(days=days)
            return (
                self.session.query(self.model_class)
                .filter(self.model_class.start_time < threshold_date)
                .all()
            )
            
        return self.execute_query(
            query_builder,
            err_msg=f"獲取超過{days}天的歷史記錄時發生錯誤"
        )
    
    def update_history_status(
        self, 
        history_id: int, 
        success: bool, 
        message: Optional[str] = None, 
        articles_count: Optional[int] = None
    ) -> bool:
        """
        更新歷史記錄的狀態
        
        :param history_id: 歷史記錄ID
        :param success: 是否成功
        :param message: 可選的訊息
        :param articles_count: 可選的文章數量
        :return: 是否更新成功
        """
        try:
            # 構建更新數據
            update_data = {'success': success, 'end_time': datetime.now(timezone.utc)}
            
            if message is not None:
                update_data['message'] = message
                
            if articles_count is not None:
                update_data['articles_count'] = articles_count
                
            # 使用更新方法
            updated_entity = self.update(history_id, update_data)
            
            # 提交事務
            self.execute_query(
                lambda: self.session.commit(),
                err_msg=f"提交更新歷史記錄ID為{history_id}的狀態時發生錯誤"
            )
            
            return updated_entity is not None
        except Exception as e:
            # 這裡不需要嵌套 execute_query，因為可能發生的異常已經在 update 方法中處理
            self.execute_query(
                lambda: self.session.rollback(),
                err_msg="回滾更新歷史記錄狀態事務時發生錯誤",
                preserve_exceptions=[]
            )
            logger.error(f"更新歷史記錄狀態時發生錯誤: {e}")
            return False

    def get_latest_by_task_id(self, task_id: int) -> Optional[CrawlerTaskHistory]:
        """獲取指定任務的最新一筆歷史記錄"""
        try:
            result = self.session.query(self.model_class).\
                filter(self.model_class.task_id == task_id).\
                order_by(self.model_class.created_at.desc()).\
                first()
            return result
        except Exception as e:
            self.session.rollback()
            error_msg = f"獲取最新歷史記錄失敗, task_id={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg) from e 