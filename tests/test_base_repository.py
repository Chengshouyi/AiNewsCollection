import pytest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base_model import Base
from src.database.base_repository import BaseRepository
from src.error.errors import  DatabaseOperationError, IntegrityValidationError
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy import String
from unittest.mock import patch
from typing import Optional
from pydantic import BaseModel, field_validator


# 測試用的 Pydantic Schema 類
class ModelCreateSchema(BaseModel):
    name: str
    title: str
    link: str
    source: str
    published_at: str
    summary: Optional[str] = None
    
    @field_validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError("title: 不能為空")
        if len(v) > 500:
            raise ValueError("title: 長度不能超過 500 字元")
        return v.strip()
    
    @field_validator('link')
    def validate_link(cls, v):
        if not v or not v.strip():
            raise ValueError("link: 不能為空")
        if len(v) > 1000:
            raise ValueError("link: 長度不能超過 1000 字元")
        return v.strip()

class ModelUpdateSchema(BaseModel):
    title: Optional[str] = None
    link: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    summary: Optional[str] = None


class ModelForTest(Base):
    """測試用模型"""
    __tablename__ = 'test_model'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    link: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    published_at: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)

class TestBaseRepository:
    
    @pytest.fixture
    def engine(self):
        """創建測試用的資料庫引擎"""
        return create_engine('sqlite:///:memory:')
    
    @pytest.fixture
    def session(self, engine):
        """創建測試用的資料庫會話"""
        Base.metadata.create_all(engine)
        session = Session(engine)
        yield session
        session.close()
        Base.metadata.drop_all(engine)
    
    @pytest.fixture
    def repo(self, session):
        """創建 TestModel 的 Repository 實例"""
        return BaseRepository(session, ModelForTest)
    
    @pytest.fixture
    def sample_model_data(self):
        """建立測試數據資料"""
        return {
            "name": "test_name",
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": "2023-07-01",
            "source": "測試來源",
            "created_at": datetime.now(timezone.utc)
        }
    
    def test_execute_query(self, repo):
        """測試 execute_query 方法"""
        # 測試正常查詢
        result = repo.execute_query(
            lambda: 5 + 5,
            err_msg="自定義錯誤訊息"
        )
        assert result == 10
        
        # 測試拋出自定義錯誤類別
        class CustomError(Exception):
            pass
            
        with pytest.raises(CustomError) as excinfo:
            repo.execute_query(
                lambda: 1/0,  # 故意引發錯誤
                exception_class=CustomError,
                err_msg="自定義錯誤"
            )
        assert "自定義錯誤" in str(excinfo.value)
        
        # 測試默認錯誤類別
        with pytest.raises(DatabaseOperationError) as excinfo:
            repo.execute_query(
                lambda: 1/0  # 故意引發錯誤
            )
        assert "資料庫操作錯誤" in str(excinfo.value)
    
    def test_create(self, repo, sample_model_data):
        """測試創建實體"""
        result = repo.create(sample_model_data)
        repo.session.commit()
        
        assert result.id is not None
        assert result.title == "測試文章"
        assert result.link == "https://test.com/article"
    
    def test_create_with_schema(self, repo, sample_model_data):
        """測試使用schema創建實體"""
        # 確保包含了 name 欄位
        schema_data = {k: v for k, v in sample_model_data.items() 
                      if k in ['name', 'title', 'link', 'published_at', 'source', 'summary']}
        result = repo.create(schema_data, schema_class=ModelCreateSchema)
        repo.session.commit()
        
        assert result.id is not None
        assert result.title == "測試文章"
        assert result.link == "https://test.com/article"
    
    def test_get_by_id(self, repo, sample_model_data):
        """測試根據ID獲取實體"""
        article = repo.create(sample_model_data)
        repo.session.commit()
        
        result = repo.get_by_id(article.id)
        assert result is not None
        assert result.id == article.id
        assert result.title == "測試文章"
    
    def test_get_all(self, repo, sample_model_data):
        """測試獲取所有實體"""
        # 創建多筆數據
        for i in range(3):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            data["link"] = f"https://test.com/article{i}"
            repo.create(data)
        repo.session.commit()
        
        results = repo.get_all()
        assert results is not None
        assert len(results) == 3
    
    def test_get_all_with_sort(self, repo, sample_model_data):
        """測試獲取所有實體並排序"""
        # 創建多筆數據
        for i in range(3):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            data["link"] = f"https://test.com/article{i}"
            repo.create(data)
        repo.session.commit()
        
        # 測試升序排序
        results = repo.get_all(sort_by="title", sort_desc=False)
        assert [item.title for item in results] == ["測試文章0", "測試文章1", "測試文章2"]
        
        # 測試降序排序
        results = repo.get_all(sort_by="title", sort_desc=True)
        assert [item.title for item in results] == ["測試文章2", "測試文章1", "測試文章0"]
    
    def test_get_all_with_limit_offset(self, repo, sample_model_data):
        """測試獲取所有實體並分頁"""
        # 創建多筆數據
        for i in range(5):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            data["link"] = f"https://test.com/article{i}"
            repo.create(data)
        repo.session.commit()
        
        # 測試限制和偏移
        results = repo.get_all(limit=2, offset=1)
        assert len(results) == 2
        assert results[0].title == "測試文章1"  # 第二條數據（索引1）
        assert results[1].title == "測試文章2"  # 第三條數據（索引2）
    
    def test_update(self, repo, sample_model_data):
        """測試更新實體"""
        entity = repo.create(sample_model_data)
        repo.session.commit()
        
        updated_data = {
            "title": "更新後的文章",
            "summary": "這是更新後的摘要"
        }
        
        result = repo.update(entity.id, updated_data)
        repo.session.commit()
        
        assert result is not None
        assert result.id == entity.id
        assert result.title == "更新後的文章"
        assert result.summary == "這是更新後的摘要"
        assert result.link == "https://test.com/article"  # 未更新的欄位應保持不變
    
    def test_update_with_schema(self, repo, sample_model_data):
        """測試使用schema更新實體"""
        entity = repo.create(sample_model_data)
        repo.session.commit()
        
        updated_data = {
            "title": "使用Schema更新後的文章",
            "summary": "這是使用Schema更新後的摘要"
        }
        
        result = repo.update(entity.id, updated_data, schema_class=ModelUpdateSchema)
        repo.session.commit()
        
        assert result is not None
        assert result.id == entity.id
        assert result.title == "使用Schema更新後的文章"
        assert result.summary == "這是使用Schema更新後的摘要"
        assert result.link == "https://test.com/article"  # 未更新的欄位應保持不變
    
    def test_update_nonexistent_entity(self, repo):
        """測試更新不存在的實體"""
        result = repo.update(999, {"title": "新標題"})
        assert result is None  # 應該返回 None 而不是拋出異常
    
    def test_delete(self, repo, sample_model_data):
        """測試刪除實體"""
        entity = repo.create(sample_model_data)
        repo.session.commit()
        
        result = repo.delete(entity.id)
        repo.session.commit()
        
        assert result is True
        assert repo.get_by_id(entity.id) is None
    
    def test_delete_nonexistent_entity(self, repo):
        """測試刪除不存在的實體"""
        result = repo.delete(999)
        assert result is False  # 應該返回 False 而不是拋出異常
    
    def test_get_paginated(self, repo, sample_model_data):
        """測試分頁功能"""
        # 創建多筆數據
        for i in range(11):  # 創建11筆，確保有多頁
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            data["link"] = f"https://test.com/article{i}"
            repo.create(data)
        repo.session.commit()
        
        # 測試第一頁
        page_data = repo.get_paginated(page=1, per_page=5)
        assert page_data["page"] == 1
        assert page_data["per_page"] == 5
        assert page_data["total"] == 11
        assert page_data["total_pages"] == 3
        assert page_data["has_next"] is True
        assert page_data["has_prev"] is False
        assert len(page_data["items"]) == 5
        
        # 測試第二頁
        page_data = repo.get_paginated(page=2, per_page=5)
        assert page_data["page"] == 2
        assert page_data["has_next"] is True
        assert page_data["has_prev"] is True
        assert len(page_data["items"]) == 5
        
        # 測試最後一頁
        page_data = repo.get_paginated(page=3, per_page=5)
        assert page_data["page"] == 3
        assert page_data["has_next"] is False
        assert page_data["has_prev"] is True
        assert len(page_data["items"]) == 1  # 最後一頁只有1筆數據
    
    def test_get_paginated_with_invalid_page(self, repo, sample_model_data):
        """測試無效的分頁參數"""
        # 創建一些測試數據
        for i in range(3):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            data["link"] = f"https://test.com/article{i}"
            repo.create(data)
        repo.session.commit()
        
        # 測試頁碼小於1
        page_data = repo.get_paginated(page=-1, per_page=2)
        assert page_data["page"] == 1  # 應該自動修正為第1頁
        
        # 測試頁碼超出範圍
        page_data = repo.get_paginated(page=999, per_page=2)
        assert page_data["page"] == 2  # 應該自動修正為最後一頁
        
        # 測試每頁數量為0
        page_data = repo.get_paginated(page=1, per_page=0)
        assert page_data["total_pages"] == 0
        assert page_data["items"] == []
    
    def test_create_with_integrity_error(self, repo, sample_model_data):
        """測試創建時發生完整性錯誤"""
        with patch.object(repo.session, 'flush', 
                         side_effect=IntegrityError("UNIQUE constraint failed: test_model.link", None, Exception())) as mock_flush:
            with repo.session.no_autoflush:  # 禁用自動 flush
                with pytest.raises(IntegrityValidationError) as excinfo:  # 改為 IntegrityValidationError
                    repo.create(sample_model_data)
                
                # 驗證錯誤訊息包含正確的錯誤類型和上下文
                error_msg = str(excinfo.value)
                assert "創建ModelForTest時" in error_msg
                assert "資料重複" in error_msg  # 根據 _handle_integrity_error 的實作
                # 確認 mock 被調用
                assert mock_flush.called
    
    def test_update_with_integrity_error(self, repo, sample_model_data):
        """測試更新時發生完整性錯誤"""
        # 先創建實體
        entity = repo.create(sample_model_data)
        repo.session.commit()
        
        # 清除 session 狀態
        repo.session.expire_all()
        
        with patch.object(repo.session, 'flush', 
                         side_effect=IntegrityError("NOT NULL constraint failed: test_model.title", None, Exception())) as mock_flush:
            with repo.session.no_autoflush:  # 禁用自動 flush
                with pytest.raises(IntegrityValidationError) as excinfo:  # 改為 IntegrityValidationError
                    repo.update(entity.id, {"title": None})
                
                # 驗證錯誤訊息
                error_msg = str(excinfo.value)
                assert "更新ModelForTest時" in error_msg
                assert "必填欄位不可為空" in error_msg  # 根據 _handle_integrity_error 的實作
                # 確認 mock 被調用
                assert mock_flush.called
    
    def test_delete_with_integrity_error(self, repo, sample_model_data):
        """測試刪除時發生完整性錯誤"""
        # 先創建實體
        entity = repo.create(sample_model_data)
        repo.session.commit()
        
        # 清除 session 狀態
        repo.session.expire_all()
        
        with patch.object(repo.session, 'flush', 
                         side_effect=IntegrityError("FOREIGN KEY constraint failed", None, Exception())) as mock_flush:
            with repo.session.no_autoflush:  # 禁用自動 flush
                with pytest.raises(IntegrityValidationError) as excinfo:  # 改為 IntegrityValidationError
                    repo.delete(entity.id)
                
                # 驗證錯誤訊息
                error_msg = str(excinfo.value)
                assert "刪除ModelForTest時" in error_msg
                assert "關聯資料不存在或無法刪除" in error_msg  # 根據 _handle_integrity_error 的實作
                # 確認 mock 被調用
                assert mock_flush.called
    
    def test_find_all_alias(self, repo, sample_model_data):
        """測試 find_all 別名方法"""
        # 創建多筆數據
        for i in range(3):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            data["link"] = f"https://test.com/article{i}"
            repo.create(data)
        repo.session.commit()
        
        # 測試 find_all 是否與 get_all 提供相同的結果
        get_all_results = repo.get_all()
        find_all_results = repo.find_all()
        
        assert len(get_all_results) == len(find_all_results)
        assert all(a.id == b.id for a, b in zip(get_all_results, find_all_results))



