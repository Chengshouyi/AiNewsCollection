import pytest
from datetime import datetime
from src.model.system_settings_service import SystemSettingsService
from tests import create_in_memory_db

@pytest.fixture(scope="function")
def create_db_instance(create_in_memory_db):
    """創建應用實例，初始化數據庫和服務"""
    db_manager = create_in_memory_db
    system_settings_service = SystemSettingsService(db_manager)
    return {
        'db_manager': db_manager,
        'system_settings_service': system_settings_service
    }

@pytest.fixture(scope="class")
def valid_settings():
    """返回有效的系統設定測試數據"""
    return {
        "crawler_name": "test crawler",
        "crawl_interval": 1,
        "is_active": True,
        "created_at": datetime.now(),
        "updated_at": None,
        "last_crawl_time": None,
    }

@pytest.fixture(scope="function")
def populated_system_settings(create_db_instance, valid_settings):
    """預先填充資料庫的系統設定服務"""
    service = create_db_instance['system_settings_service']

      # 清空現有資料
    existing_settings = service.get_all_system_settings()
    for setting in existing_settings:
        service.delete_system_settings(setting['id'])

    settings_list = [
        {"crawler_name": f"test crawler {i}", 
         "crawl_interval": i, 
         "is_active": i % 2 == 0} 
        for i in range(1, 6)
    ]

    service.insert_system_settings(valid_settings)
    for settings in settings_list:
        service.insert_system_settings(settings)

    return service

class TestSystemSettingsInsert:
    """測試系統設定的插入功能"""

    def test_insert_system_settings(self, create_db_instance, valid_settings):
        service = create_db_instance['system_settings_service']
        inserted = service.insert_system_settings(valid_settings)
        assert inserted is not None
        assert inserted['id'] is not None
        assert inserted['crawler_name'] == valid_settings['crawler_name']
        assert inserted['crawl_interval'] == valid_settings['crawl_interval']
        assert inserted['is_active'] == valid_settings['is_active']
        
        retrieved = service.get_system_settings_by_id(inserted['id'])
        assert retrieved is not None
        assert retrieved['crawler_name'] == valid_settings['crawler_name']

    def test_insert_duplicate_system_settings(self, create_db_instance, valid_settings):
        service = create_db_instance['system_settings_service']

        # 確保資料庫中沒有重複的設定
        existing_settings = service.get_all_system_settings()
        for setting in existing_settings:
            service.delete_system_settings(setting['id'])

        first_insert = service.insert_system_settings(valid_settings)
        assert first_insert is not None

        second_insert = service.insert_system_settings(valid_settings)
        assert second_insert is None

    def test_insert_invalid_system_settings(self, create_db_instance):
        service = create_db_instance['system_settings_service']
        invalid_data = [
            {"crawl_interval": 1},
            {"crawler_name": "", "crawl_interval": -1, "is_active": True}
        ]
        for data in invalid_data:
            result = service.insert_system_settings(data)
            assert result is None

class TestSystemSettingsRetrieval:
    """測試系統設定的查詢功能"""

    def test_get_system_settings_by_id(self, populated_system_settings):
        all_settings = populated_system_settings.get_all_system_settings()
        setting_id = all_settings[0]['id']
        setting = populated_system_settings.get_system_settings_by_id(setting_id)
        assert setting is not None
        assert setting['id'] == setting_id
        
        assert populated_system_settings.get_system_settings_by_id(9999) is None
        
        invalid_ids = [0, -1, "abc"]
        for invalid_id in invalid_ids:
            assert populated_system_settings.get_system_settings_by_id(invalid_id) is None

    def test_get_all_system_settings(self, populated_system_settings):
        all_settings = populated_system_settings.get_all_system_settings()
        assert len(all_settings) >= 6
        
        limited_settings = populated_system_settings.get_all_system_settings(limit=3)
        assert len(limited_settings) == 3
        
        offset_settings = populated_system_settings.get_all_system_settings(offset=2)
        assert len(offset_settings) == len(all_settings) - 2
        
        asc_settings = populated_system_settings.get_all_system_settings(sort_by="crawler_name", sort_desc=False)
        desc_settings = populated_system_settings.get_all_system_settings(sort_by="crawler_name", sort_desc=True)
        assert asc_settings[0]['crawler_name'] < desc_settings[0]['crawler_name']

    def test_search_system_settings(self, populated_system_settings):
        search_result = populated_system_settings.search_system_settings({"crawler_name": "test crawler 1"})
        assert len(search_result) >= 1
        assert any("test crawler 1" in setting['crawler_name'] for setting in search_result)
        
        active_settings = populated_system_settings.search_system_settings({"is_active": True})
        inactive_settings = populated_system_settings.search_system_settings({"is_active": False})
        assert len(active_settings) > 0
        assert len(inactive_settings) > 0
        assert all(setting['is_active'] for setting in active_settings)
        assert all(not setting['is_active'] for setting in inactive_settings)
        
        combined_search = populated_system_settings.search_system_settings({
            "crawler_name": "test",
            "is_active": True
        })
        assert all("test" in setting['crawler_name'] and setting['is_active'] for setting in combined_search)
        
        paginated_search = populated_system_settings.search_system_settings({"crawler_name": "test"}, limit=2)
        assert len(paginated_search) <= 2

    def test_get_system_settings_paginated(self, populated_system_settings):
        page_result = populated_system_settings.get_system_settings_paginated(page=1, per_page=3)
        assert all(key in page_result for key in ["items", "total", "page", "per_page", "total_pages"])
        assert len(page_result["items"]) <= 3
        assert page_result["page"] == 1
        assert page_result["per_page"] == 3
        
        page_result_2 = populated_system_settings.get_system_settings_paginated(page=2, per_page=3)
        assert page_result_2["page"] == 2
        
        page_1_ids = [item['id'] for item in page_result["items"]]
        page_2_ids = [item['id'] for item in page_result_2["items"]]
        assert not any(id in page_2_ids for id in page_1_ids)
        
        sorted_page = populated_system_settings.get_system_settings_paginated(
            page=1, per_page=3, sort_by="crawl_interval", sort_desc=True
        )
        assert all(sorted_page["items"][i]["crawl_interval"] >= sorted_page["items"][i+1]["crawl_interval"] 
                  for i in range(len(sorted_page["items"])-1))

class TestSystemSettingsUpdate:
    """測試系統設定的更新功能"""

    def test_update_system_settings(self, populated_system_settings):
        all_settings = populated_system_settings.get_all_system_settings()
        original = all_settings[0]
        setting_id = original['id']
        original_created_at = original['created_at']
        
        updated_data = {
            'crawler_name': 'updated crawler name',
            'crawl_interval': 42,
            'is_active': not original['is_active']
        }
        updated = populated_system_settings.update_system_settings(setting_id, updated_data)
        assert updated is not None
        assert updated['crawler_name'] == updated_data['crawler_name']
        assert updated['crawl_interval'] == updated_data['crawl_interval']
        assert updated['is_active'] == updated_data['is_active']
        assert updated['created_at'] == original_created_at
        assert updated['updated_at'] is not None
        
        assert populated_system_settings.update_system_settings(9999, updated_data) is None
        assert populated_system_settings.update_system_settings(-1, updated_data) is None
        
        updated_setting = populated_system_settings.get_system_settings_by_id(setting_id)
        try_update = populated_system_settings.update_system_settings(setting_id, {'created_at': datetime.now()})
        retrieved = populated_system_settings.get_system_settings_by_id(setting_id)
        assert retrieved['created_at'] == original_created_at

    def test_update_system_settings_invalid_data(self, populated_system_settings):
        all_settings = populated_system_settings.get_all_system_settings()
        setting_id = all_settings[0]['id']
        invalid_updates = [
            {'crawler_name': ''},
            {'crawl_interval': -1},
            {'is_active': 'not_a_boolean'}
        ]
        for invalid_update in invalid_updates:
            assert populated_system_settings.update_system_settings(setting_id, invalid_update) is None

    def test_batch_update_system_settings(self, populated_system_settings):
        all_settings = populated_system_settings.get_all_system_settings()
        setting_ids = [all_settings[0]['id'], all_settings[1]['id']]
        update_data = {'is_active': False, 'crawl_interval': 999}
        
        success_count, fail_count = populated_system_settings.batch_update_system_settings(setting_ids, update_data)
        assert success_count == 2
        assert fail_count == 0
        
        for setting_id in setting_ids:
            updated = populated_system_settings.get_system_settings_by_id(setting_id)
            assert updated['is_active'] == False
            assert updated['crawl_interval'] == 999
        
        mixed_ids = [all_settings[0]['id'], 9999]
        success_count, fail_count = populated_system_settings.batch_update_system_settings(mixed_ids, update_data)
        assert success_count == 1
        assert fail_count == 1

class TestSystemSettingsDeletion:
    """測試系統設定的刪除功能"""

    def test_delete_system_settings(self, populated_system_settings):
        all_settings = populated_system_settings.get_all_system_settings()
        setting_id = all_settings[0]['id']
        
        assert populated_system_settings.delete_system_settings(setting_id) is True
        assert populated_system_settings.get_system_settings_by_id(setting_id) is None
        
        assert populated_system_settings.delete_system_settings(9999) is False
        
        invalid_ids = [0, -1, "abc"]
        for invalid_id in invalid_ids:
            assert populated_system_settings.delete_system_settings(invalid_id) is False

    def test_batch_delete_system_settings(self, populated_system_settings):
        all_settings = populated_system_settings.get_all_system_settings()
        setting_ids = [all_settings[0]['id'], all_settings[1]['id']]
        
        success_count, fail_count = populated_system_settings.batch_delete_system_settings(setting_ids)
        assert success_count == 2
        assert fail_count == 0
        
        for setting_id in setting_ids:
            assert populated_system_settings.get_system_settings_by_id(setting_id) is None
        
        remaining_settings = populated_system_settings.get_all_system_settings()
        mixed_ids = [remaining_settings[0]['id'], 9999]
        success_count, fail_count = populated_system_settings.batch_delete_system_settings(mixed_ids)
        assert success_count == 1
        assert fail_count == 1

class TestSystemSettingsUtilities:
    """測試系統設定的工具功能"""

    def test_sys_settings_to_dict(self, populated_system_settings):
        all_settings = populated_system_settings.get_all_system_settings()
        setting = all_settings[0]
        
        result = populated_system_settings._sys_settings_to_dict(setting)
        assert result is not None
        assert result == setting
        
        assert populated_system_settings._sys_settings_to_dict(None) is None
        
        with populated_system_settings.db_manager.session_scope() as session:
            from src.model.models import SystemSettings
            setting_entity = session.query(SystemSettings).filter_by(id=setting['id']).first()
            result = populated_system_settings._sys_settings_to_dict(setting_entity)
            assert result is not None
            assert result['id'] == setting['id']
            assert result['crawler_name'] == setting['crawler_name']

    def test_error_handling(self, create_db_instance, valid_settings):
        service = create_db_instance['system_settings_service']
        
        try:
            result = service.get_all_system_settings()
            assert result == []
        except Exception as e:
            pytest.fail(f"獲取空數據庫中的系統設定時不應拋出異常: {e}")