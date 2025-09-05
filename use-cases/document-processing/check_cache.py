#!/usr/bin/env python3
from smolcrawl.utils import get_cache

cache = get_cache('crawl')
print(f'Cache directory: {cache.directory}')
print(f'Cache volume: {cache.volume()}')
print('All keys in cache:')
keys = list(cache)
print(f'Number of keys: {len(keys)}')
for key in keys:
    print(f'  {key}')
    
if keys:
    # Try to get data for the first key
    first_key = keys[0]
    data = cache.get(first_key)
    if data:
        print(f'First key data type: {type(data)}')
        if isinstance(data, list):
            print(f'Number of pages in first key: {len(data)}')
        elif hasattr(data, '__len__'):
            print(f'Data length: {len(data)}')
