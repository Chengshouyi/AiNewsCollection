import json
import os
import pytest

def load_config(file_path="src/crawlers/configs/bnext_crawler_config.json"):
    """從 JSON 檔案載入設定"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"設定檔 '{file_path}' 未找到")
    except json.JSONDecodeError:
        raise json.JSONDecodeError(f"設定檔 '{file_path}' JSON 格式錯誤", "", 0)

def test_config_structure():
    """測試設定檔的基本結構"""
    config = load_config()
    assert isinstance(config, dict)
    assert "name" in config
    assert "base_url" in config
    assert "list_url_template" in config
    assert "categories" in config
    assert "full_categories" in config
    assert "valid_domains" in config
    assert "url_patterns" in config
    assert "url_file_extensions" in config
    assert "date_format" in config
    assert "selectors" in config

def test_config_values():
    """測試設定檔中的特定值"""
    config = load_config()
    assert config["name"] == "bnext"
    assert config["base_url"] == "https://www.bnext.com.tw"
    assert config["list_url_template"] == "{base_url}/categories/{category}"
    assert isinstance(config["categories"], list)
    assert "ai" in config["categories"]
    assert isinstance(config["full_categories"], list)
    assert "cloudcomputing" in config["full_categories"]
    assert isinstance(config["valid_domains"], list)
    assert "https://www.bnext.com.tw" in config["valid_domains"]
    assert isinstance(config["url_patterns"], list)
    assert "/categories/" in config["url_patterns"]
    assert "/articles/" in config["url_patterns"]
    assert isinstance(config["url_file_extensions"], list)
    assert ".html" in config["url_file_extensions"]
    assert config["date_format"] == "%Y-%m-%d"
    assert isinstance(config["selectors"], dict)
    assert "get_article_links" in config["selectors"]
    assert "get_article_contents" in config["selectors"]

def test_selectors_structure():
    """測試 selectors 的內部結構"""
    config = load_config()
    assert isinstance(config["selectors"]["get_article_links"], dict)
    assert "articles_container" in config["selectors"]["get_article_links"]
    assert "link" in config["selectors"]["get_article_links"]
    assert "category" in config["selectors"]["get_article_links"]
    assert "title" in config["selectors"]["get_article_links"]
    assert "summary" in config["selectors"]["get_article_links"]
    assert "published_age" in config["selectors"]["get_article_links"]
    assert isinstance(config["selectors"]["get_article_links"].get("article_grid_container"), dict)
    assert "container" in config["selectors"]["get_article_links"]["article_grid_container"]
    assert "link" in config["selectors"]["get_article_links"]["article_grid_container"]
    assert "title" in config["selectors"]["get_article_links"]["article_grid_container"]
    assert "summary" in config["selectors"]["get_article_links"]["article_grid_container"]
    assert "published_age" in config["selectors"]["get_article_links"]["article_grid_container"]

    assert isinstance(config["selectors"]["get_article_contents"], dict)
    assert "content_container" in config["selectors"]["get_article_contents"]
    assert "published_date" in config["selectors"]["get_article_contents"]
    assert "category" in config["selectors"]["get_article_contents"]
    assert "title" in config["selectors"]["get_article_contents"]
    assert "summary" in config["selectors"]["get_article_contents"]
    assert "author" in config["selectors"]["get_article_contents"]
    assert "content" in config["selectors"]["get_article_contents"]
    assert isinstance(config["selectors"]["get_article_contents"].get("tags"), dict)
    assert "container" in config["selectors"]["get_article_contents"]["tags"]
    assert "tag" in config["selectors"]["get_article_contents"]["tags"]

def test_load_config_not_found():
    """測試當 JSON 檔案不存在時是否拋出 FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        load_config("non_existent_config.json")

def test_load_config_invalid_json():
    """測試當 JSON 檔案格式錯誤時是否拋出 json.JSONDecodeError"""
    with open("invalid_config.json", 'w') as f:
        f.write("this is not valid json")
    try:
        with pytest.raises(json.JSONDecodeError):
            load_config("invalid_config.json")
    finally:
        os.remove("invalid_config.json") # 清理創建的無效檔案