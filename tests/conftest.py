from src.crawler.site_config import SiteConfig

def pytest_configure() -> SiteConfig:
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
