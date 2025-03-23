import pytest
import shutil
import os

def pytest_configure(config):
    """Clear pytest cache at the start of every test session."""
    # Get the cache directory
    cache_dir = config.cache.makedir(".pytest_cache")
    
    # Clear the cache directory
    for item in os.listdir(cache_dir):
        path = os.path.join(cache_dir, item)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
            
    print("Pytest cache cleared!")

"""def pytest_configure() -> SiteConfig:
    from src.crawler.site_config import SiteConfig
    return SiteConfig(
        name='test',
        base_url='https://example.com',
        list_url_template='{base_url}/categories/{category}',
        valid_domains=['https://example.com'],
        url_patterns=['/categories/', '/articles/'],
        url_file_extensions=['.html', ''],
        date_format='%Y-%m-%d',
        selectors={
            'list': [],
        'content': [],
        'date': [],
            'title': [],
            'pagination': []
        }
    )
"""