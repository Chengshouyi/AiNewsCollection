from pydantic import ValidationError
import pytest
from datetime import datetime, timedelta
from src.model.models import Base, SystemSettings
from src.model.database_manager import DatabaseManager
from src.model.system_settings_service import SystemSettingsService
from src.model.system_settings_schema import SystemSettingsCreateSchema, SystemSettingsUpdateSchema
from src.model.repository import Repository


@pytest.fixture
def create_app():
    """創建應用實例，初始化數據庫和服務"""
    db_manager = DatabaseManager(db_path="sqlite:///:memory:")
    db_manager.create_tables(Base)
    system_settings_service = SystemSettingsService(db_manager)
    return {
        'db_manager': db_manager,
        'system_settings_service': system_settings_service
    }

def get_test_system_settings_data(
    crawler_name="test crawler",
    crawl_interval=1,
    is_active=True,
    created_at=datetime.now(),  
    updated_at=datetime.now() + timedelta(days=1),
    last_crawl_time=datetime.now() + timedelta(days=1),
):
    return {
        "crawler_name": crawler_name,
        "crawl_interval": crawl_interval,
        "is_active": is_active,
        "created_at": created_at,
        "updated_at": updated_at,
        "last_crawl_time": last_crawl_time,
    }

def test_insert_system_settings(create_app):
    """測試插入系統設定"""
    system_settings_service = create_app['system_settings_service']
    system_settings_data = get_test_system_settings_data()
    
    # 插入系統設定
    inserted_system_settings = system_settings_service.insert_system_settings(system_settings_data)
    assert inserted_system_settings is not None

    # 驗證系統設定是否插入成功
    system_settings = system_settings_service.get_system_settings_by_id(inserted_system_settings['id'])
    assert system_settings is not None
    assert system_settings['crawler_name'] == "test crawler"
    assert system_settings['crawl_interval'] == 1
    assert system_settings['is_active'] == True


def test_get_all_system_settings(create_app):
    """測試獲取所有系統設定"""
    system_settings_service = create_app['system_settings_service']
    system_settings_data = get_test_system_settings_data()
    
    # 插入系統設定
    inserted_system_settings = system_settings_service.insert_system_settings(system_settings_data)
    assert inserted_system_settings is not None

    # 獲取所有系統設定
    all_system_settings = system_settings_service.get_all_system_settings()
    assert len(all_system_settings) == 1
    assert all_system_settings[0]['crawler_name'] == "test crawler" 
    assert all_system_settings[0]['crawl_interval'] == 1
    assert all_system_settings[0]['is_active'] == True

    
def test_update_system_settings(create_app):
    """測試更新系統設定"""
    system_settings_service = create_app['system_settings_service']
    system_settings_data = get_test_system_settings_data()
    
    # 插入系統設定
    inserted_system_settings = system_settings_service.insert_system_settings(system_settings_data)
    assert inserted_system_settings is not None

    original_created_at = inserted_system_settings['created_at']
    
    # 更新系統設定
    updated_system_settings = system_settings_service.update_system_settings(inserted_system_settings['id'], {'crawler_name': 'updated crawler'})
    assert updated_system_settings is not None

    # 驗證系統設定是否更新成功
    system_settings = system_settings_service.get_system_settings_by_id(inserted_system_settings['id'])
    assert system_settings is not None
    assert system_settings['crawler_name'] == 'updated crawler' 
    assert system_settings['crawl_interval'] == 1
    assert system_settings['is_active'] == True


    # 驗證 created_at 未被修改
    system_settings = system_settings_service.get_system_settings_by_id(inserted_system_settings['id'])
    assert system_settings['created_at'] == original_created_at

def test_batch_update_system_settings(create_app):
    """測試批量更新系統設定"""
    system_settings_service = create_app['system_settings_service']
    system_settings_data = get_test_system_settings_data()
    
    # 插入系統設定
    inserted_system_settings = system_settings_service.insert_system_settings(system_settings_data)
    assert inserted_system_settings is not None

    # 批量更新系統設定
    updated_system_settings = system_settings_service.batch_update_system_settings([inserted_system_settings['id']], {'crawler_name': 'updated crawler'})
    assert updated_system_settings is not None

    # 驗證系統設定是否更新成功
    system_settings = system_settings_service.get_system_settings_by_id(inserted_system_settings['id'])
    assert system_settings is not None
    assert system_settings['crawler_name'] == 'updated crawler'
    assert system_settings['crawl_interval'] == 1
    assert system_settings['is_active'] == True

    
def test_delete_system_settings(create_app):
    """測試刪除系統設定"""
    system_settings_service = create_app['system_settings_service']
    system_settings_data = get_test_system_settings_data()
    
    # 插入系統設定
    inserted_system_settings = system_settings_service.insert_system_settings(system_settings_data)
    assert inserted_system_settings is not None
    
    # 刪除系統設定
    deleted_system_settings = system_settings_service.delete_system_settings(inserted_system_settings['id'])
    assert deleted_system_settings is not None

    # 驗證系統設定是否刪除成功
    system_settings = system_settings_service.get_system_settings_by_id(inserted_system_settings['id'])
    assert system_settings is None  
    
def test_batch_delete_system_settings(create_app):
    """測試批量刪除系統設定"""
    system_settings_service = create_app['system_settings_service']
    system_settings_data = get_test_system_settings_data()
    
    # 插入系統設定
    inserted_system_settings = system_settings_service.insert_system_settings(system_settings_data)
    assert inserted_system_settings is not None
    
    # 批量刪除系統設定
    deleted_system_settings = system_settings_service.batch_delete_system_settings([inserted_system_settings['id']])    
    assert deleted_system_settings is not None

    # 驗證系統設定是否刪除成功
    system_settings = system_settings_service.get_system_settings_by_id(inserted_system_settings['id'])
    assert system_settings is None  
    
def test_sys_settings_to_dict(create_app):
    """測試將系統設定轉換為字典"""
    system_settings_service = create_app['system_settings_service']
    system_settings_data = get_test_system_settings_data()
    
    # 插入系統設定
    inserted_system_settings = system_settings_service.insert_system_settings(system_settings_data)
    assert inserted_system_settings is not None
    
    # 將系統設定轉換為字典
    system_settings_dict = system_settings_service._sys_settings_to_dict(inserted_system_settings)
    assert system_settings_dict is not None
    assert system_settings_dict['id'] is not None
    assert system_settings_dict['crawler_name'] == "test crawler"
    assert system_settings_dict['crawl_interval'] == 1
    assert system_settings_dict['is_active'] == True


def test_sys_settings_to_dict_none(create_app):
    """測試將空系統設定轉換為字典"""
    system_settings_service = create_app['system_settings_service']
    system_settings_dict = system_settings_service._sys_settings_to_dict(None)
    assert system_settings_dict is None
    
def test_sys_settings_to_dict_exception(create_app):
    """測試將系統設定轉換為字典時的異常情況"""
    system_settings_service = create_app['system_settings_service']
    system_settings_dict = system_settings_service._sys_settings_to_dict(None)
    assert system_settings_dict is None

def test_sys_settings_to_dict_exception_handling(create_app):
    """測試將系統設定轉換為字典時的異常情況"""
    system_settings_service = create_app['system_settings_service']
    system_settings_dict = system_settings_service._sys_settings_to_dict(None)
    assert system_settings_dict is None
    
    






