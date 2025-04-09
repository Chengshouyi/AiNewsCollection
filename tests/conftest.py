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

