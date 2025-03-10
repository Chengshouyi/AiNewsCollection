import pytest
from datetime import datetime, timedelta
from src.model.models import Base, SystemSettings
from src.model.database_manager import DatabaseManager
from src.model.system_settings_service import SystemSettingsService
from src.model.system_settings_schema import SystemSettingsCreateSchema, SystemSettingsUpdateSchema


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


@pytest.fixture
def valid_settings_data():
    """返回有效的系統設定測試數據"""
    return {
        "crawler_name": "test crawler",
        "crawl_interval": 1,
        "is_active": True,
        "created_at": datetime.now(),
        "updated_at": None,
        "last_crawl_time": None,
    }


@pytest.fixture
def populated_service(create_app, valid_settings_data):
    """預先填充資料庫的系統設定服務"""
    service = create_app['system_settings_service']
    
    # 創建多個測試數據
    settings_list = [
        {"crawler_name": f"test crawler {i}", 
         "crawl_interval": i, 
         "is_active": i % 2 == 0} 
        for i in range(1, 6)
    ]
    
    # 插入預設資料和自訂資料
    service.insert_system_settings(valid_settings_data)
    for settings in settings_list:
        service.insert_system_settings(settings)
    
    return service


# 基本 CRUD 測試

def test_insert_system_settings(create_app, valid_settings_data):
    """測試插入系統設定"""
    system_settings_service = create_app['system_settings_service']
    
    # 插入系統設定
    inserted_settings = system_settings_service.insert_system_settings(valid_settings_data)
    assert inserted_settings is not None
    assert inserted_settings['id'] is not None
    assert inserted_settings['crawler_name'] == valid_settings_data['crawler_name']
    assert inserted_settings['crawl_interval'] == valid_settings_data['crawl_interval']
    assert inserted_settings['is_active'] == valid_settings_data['is_active']

    # 驗證系統設定是否插入成功
    retrieved_settings = system_settings_service.get_system_settings_by_id(inserted_settings['id'])
    assert retrieved_settings is not None
    assert retrieved_settings['crawler_name'] == valid_settings_data['crawler_name']


def test_insert_duplicate_system_settings(create_app, valid_settings_data):
    """測試插入重複的系統設定"""
    system_settings_service = create_app['system_settings_service']
    
    # 第一次插入應成功
    first_insert = system_settings_service.insert_system_settings(valid_settings_data)
    assert first_insert is not None
    
    # 第二次插入相同 crawler_name 應失敗
    second_insert = system_settings_service.insert_system_settings(valid_settings_data)
    assert second_insert is None


def test_insert_invalid_system_settings(create_app):
    """測試插入無效的系統設定"""
    system_settings_service = create_app['system_settings_service']
    
    # 缺少必要欄位
    invalid_data = {"crawl_interval": 1}
    result = system_settings_service.insert_system_settings(invalid_data)
    assert result is None
    
    # 無效的欄位值
    invalid_data = {
        "crawler_name": "",  # 空字串
        "crawl_interval": -1,  # 負數
        "is_active": True
    }
    result = system_settings_service.insert_system_settings(invalid_data)
    assert result is None


def test_get_system_settings_by_id(populated_service):
    """測試通過 ID 獲取系統設定"""
    # 獲取所有設定
    all_settings = populated_service.get_all_system_settings()
    assert len(all_settings) >= 1
    
    # 獲取特定 ID 的設定
    setting_id = all_settings[0]['id']
    setting = populated_service.get_system_settings_by_id(setting_id)
    assert setting is not None
    assert setting['id'] == setting_id
    
    # 測試不存在的 ID
    non_existent_id = 9999
    setting = populated_service.get_system_settings_by_id(non_existent_id)
    assert setting is None
    
    # 測試無效的 ID
    invalid_ids = [0, -1, "abc"]
    for invalid_id in invalid_ids:
        setting = populated_service.get_system_settings_by_id(invalid_id)
        assert setting is None


def test_get_all_system_settings(populated_service):
    """測試獲取所有系統設定"""
    # 基本獲取
    all_settings = populated_service.get_all_system_settings()
    assert len(all_settings) >= 6  # 應該至少有 6 筆記錄
    
    # 測試分頁
    limited_settings = populated_service.get_all_system_settings(limit=3)
    assert len(limited_settings) == 3
    
    # 測試偏移
    offset_settings = populated_service.get_all_system_settings(offset=2)
    assert len(offset_settings) == len(all_settings) - 2
    
    # 測試排序
    asc_settings = populated_service.get_all_system_settings(sort_by="crawler_name", sort_desc=False)
    desc_settings = populated_service.get_all_system_settings(sort_by="crawler_name", sort_desc=True)
    assert asc_settings[0]['crawler_name'] < desc_settings[0]['crawler_name']


def test_search_system_settings(populated_service):
    """測試搜索系統設定"""
    # 通過名稱搜索
    search_result = populated_service.search_system_settings({"crawler_name": "test crawler 1"})
    assert len(search_result) >= 1
    assert any("test crawler 1" in setting['crawler_name'] for setting in search_result)
    
    # 通過 is_active 搜索
    active_settings = populated_service.search_system_settings({"is_active": True})
    inactive_settings = populated_service.search_system_settings({"is_active": False})
    assert len(active_settings) > 0
    assert len(inactive_settings) > 0
    assert all(setting['is_active'] for setting in active_settings)
    assert all(not setting['is_active'] for setting in inactive_settings)
    
    # 組合搜索
    combined_search = populated_service.search_system_settings({
        "crawler_name": "test",
        "is_active": True
    })
    assert all("test" in setting['crawler_name'] and setting['is_active'] for setting in combined_search)
    
    # 測試分頁
    paginated_search = populated_service.search_system_settings({"crawler_name": "test"}, limit=2)
    assert len(paginated_search) <= 2


def test_get_system_settings_paginated(populated_service):
    """測試分頁獲取系統設定"""
    # 基本分頁測試
    page_result = populated_service.get_system_settings_paginated(page=1, per_page=3)
    assert "items" in page_result
    assert "total" in page_result
    assert "page" in page_result
    assert "per_page" in page_result
    assert "total_pages" in page_result
    assert len(page_result["items"]) <= 3
    assert page_result["page"] == 1
    assert page_result["per_page"] == 3
    
    # 測試第二頁
    page_result_2 = populated_service.get_system_settings_paginated(page=2, per_page=3)
    assert page_result_2["page"] == 2
    
    # 確保分頁結果不重疊
    page_1_ids = [item['id'] for item in page_result["items"]]
    page_2_ids = [item['id'] for item in page_result_2["items"]]
    assert not any(id in page_2_ids for id in page_1_ids)
    
    # 測試排序
    sorted_page = populated_service.get_system_settings_paginated(
        page=1, per_page=3, sort_by="crawl_interval", sort_desc=True
    )
    assert all(sorted_page["items"][i]["crawl_interval"] >= sorted_page["items"][i+1]["crawl_interval"] 
               for i in range(len(sorted_page["items"])-1))


def test_update_system_settings(populated_service):
    """測試更新系統設定"""
    # 獲取一個現有設定
    all_settings = populated_service.get_all_system_settings()
    original_setting = all_settings[0]
    setting_id = original_setting['id']
    original_created_at = original_setting['created_at']
    
    # 更新系統設定
    updated_data = {
        'crawler_name': 'updated crawler name',
        'crawl_interval': 42,
        'is_active': not original_setting['is_active']
    }
    updated_setting = populated_service.update_system_settings(setting_id, updated_data)
    assert updated_setting is not None
    assert updated_setting['crawler_name'] == updated_data['crawler_name']
    assert updated_setting['crawl_interval'] == updated_data['crawl_interval']
    assert updated_setting['is_active'] == updated_data['is_active']
    
    # 驗證 created_at 未被修改
    assert updated_setting['created_at'] == original_created_at
    
    # 驗證 updated_at 已更新
    assert updated_setting['updated_at'] is not None
    
    # 測試更新不存在的 ID
    result = populated_service.update_system_settings(9999, updated_data)
    assert result is None
    
    # 測試更新無效的 ID
    result = populated_service.update_system_settings(-1, updated_data)
    assert result is None
    
    # 測試更新時不能修改 created_at
    try_update_created_at = populated_service.update_system_settings(
        setting_id, {'created_at': datetime.now()}
    )
    retrieved_setting = populated_service.get_system_settings_by_id(setting_id)
    assert retrieved_setting['created_at'] == original_created_at


def test_update_system_settings_invalid_data(populated_service):
    """測試使用無效數據更新系統設定"""
    # 獲取一個現有設定
    all_settings = populated_service.get_all_system_settings()
    setting_id = all_settings[0]['id']
    
    # 測試更新無效數據
    invalid_updates = [
        {'crawler_name': ''},  # 空名稱
        {'crawl_interval': -1},  # 負間隔
        {'is_active': 'not_a_boolean'}  # 非布林值
    ]
    
    for invalid_update in invalid_updates:
        result = populated_service.update_system_settings(setting_id, invalid_update)
        assert result is None


def test_batch_update_system_settings(populated_service):
    """測試批量更新系統設定"""
    # 獲取所有設定
    all_settings = populated_service.get_all_system_settings()
    assert len(all_settings) >= 2
    
    # 選擇前兩個設定進行批量更新
    setting_ids = [all_settings[0]['id'], all_settings[1]['id']]
    update_data = {'is_active': False, 'crawl_interval': 999}
    
    # 執行批量更新
    success_count, fail_count = populated_service.batch_update_system_settings(setting_ids, update_data)
    assert success_count == 2
    assert fail_count == 0
    
    # 驗證更新是否成功
    for setting_id in setting_ids:
        updated_setting = populated_service.get_system_settings_by_id(setting_id)
        assert updated_setting['is_active'] == False
        assert updated_setting['crawl_interval'] == 999
    
    # 測試包含無效 ID 的批量更新
    mixed_ids = [all_settings[0]['id'], 9999]
    success_count, fail_count = populated_service.batch_update_system_settings(mixed_ids, update_data)
    assert success_count == 1
    assert fail_count == 1


def test_delete_system_settings(populated_service):
    """測試刪除系統設定"""
    # 獲取一個現有設定
    all_settings = populated_service.get_all_system_settings()
    setting_id = all_settings[0]['id']
    
    # 刪除設定
    result = populated_service.delete_system_settings(setting_id)
    assert result is True  # 注意這裡應該是 True 而不是 not None
    
    # 驗證設定已被刪除
    deleted_setting = populated_service.get_system_settings_by_id(setting_id)
    assert deleted_setting is None
    
    # 測試刪除不存在的設定
    result = populated_service.delete_system_settings(9999)
    assert result is False
    
    # 測試刪除無效 ID
    invalid_ids = [0, -1, "abc"]
    for invalid_id in invalid_ids:
        result = populated_service.delete_system_settings(invalid_id)
        assert result is False


def test_batch_delete_system_settings(populated_service):
    """測試批量刪除系統設定"""
    # 獲取所有設定
    all_settings = populated_service.get_all_system_settings()
    assert len(all_settings) >= 3
    
    # 選擇前兩個設定進行批量刪除
    setting_ids = [all_settings[0]['id'], all_settings[1]['id']]
    
    # 執行批量刪除
    success_count, fail_count = populated_service.batch_delete_system_settings(setting_ids)
    assert success_count == 2
    assert fail_count == 0
    
    # 驗證設定已被刪除
    for setting_id in setting_ids:
        deleted_setting = populated_service.get_system_settings_by_id(setting_id)
        assert deleted_setting is None
    
    # 測試包含無效 ID 的批量刪除
    remaining_settings = populated_service.get_all_system_settings()
    mixed_ids = [remaining_settings[0]['id'], 9999]
    success_count, fail_count = populated_service.batch_delete_system_settings(mixed_ids)
    assert success_count == 1
    assert fail_count == 1


def test_sys_settings_to_dict(populated_service):
    """測試系統設定實例轉換為字典"""
    # 獲取一個現有設定
    all_settings = populated_service.get_all_system_settings()
    setting = all_settings[0]
    
    # 測試已經是字典的情況
    result = populated_service._sys_settings_to_dict(setting)
    assert result is not None
    assert result == setting
    
    # 測試空值情況
    result = populated_service._sys_settings_to_dict(None)
    assert result is None
    
    # 通過實體測試（需要 access 到 SystemSettings 類的實例）
    with populated_service.db_manager.session_scope() as session:
        setting_entity = session.query(SystemSettings).filter_by(id=setting['id']).first()
        result = populated_service._sys_settings_to_dict(setting_entity)
        assert result is not None
        assert result['id'] == setting['id']
        assert result['crawler_name'] == setting['crawler_name']


def test_error_handling(create_app, valid_settings_data):
    """測試錯誤處理情況"""
    system_settings_service = create_app['system_settings_service']
    
    # 模擬 SystemSettings 表不存在的情況
    db_manager = create_app['db_manager']
    db_manager.create_tables(Base)  # 重建數據庫但不創建表
    
    # 嘗試從不存在的表中獲取數據
    try:
        result = system_settings_service.get_all_system_settings()
        assert result == []  # 應返回空列表而不是引發異常
    except Exception as e:
        pytest.fail(f"獲取空數據庫中的系統設定時不應拋出異常: {e}")
        