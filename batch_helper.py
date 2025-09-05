#!/usr/bin/env python3
"""Helper script for batch file operations"""

import sys
import json
from pathlib import Path

def create_test_urls(input_file, output_file, count=5):
    """Extract first N URLs from discovered URLs file"""
    try:
        with open(input_file, 'r') as f:
            urls = f.readlines()[:count]
        with open(output_file, 'w') as f:
            f.writelines(urls)
        print(f'✅ Created test set with {len(urls)} URLs')
        return True
    except Exception as e:
        print(f'❌ Failed to create test URLs: {e}')
        return False

def create_test_config(base_url, url_file='quick_test_urls.txt', output_file='quick_test_config.json'):
    """Create a test configuration file"""
    config = {
        'base_url': base_url,
        'url_list_file': url_file,
        'start_urls': None,
        'max_workers': 2,
        'max_retries': 2,
        'timeout': 10,
        'delay_between_requests': 0.5,
        'output_dir': 'output/quick-test',
        'merge_output': 'output/quick-test/merged_documentation.md',
        'categories': ['Documentation', 'Guides', 'API', 'Other'],
        'category_order': ['Documentation', 'Guides', 'API', 'Other'],
        'clean_content': True,
        'add_metadata': True,
        'use_readability': True,
        'convert_to_markdown': True,
        'include_toc': True
    }
    
    try:
        with open(output_file, 'w') as f:
            json.dump(config, f, indent=4)
        print('✅ Test config created')
        return True
    except Exception as e:
        print(f'❌ Failed to create config: {e}')
        return False

def update_use_case_config(use_case_name):
    """Update use case config to use discovered URLs"""
    config_file = f'use-cases/{use_case_name}/config.json'
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        config['url_list_file'] = 'discovered_urls.txt'
        config['start_urls'] = None
        config['max_workers'] = 6
        config['delay_between_requests'] = 0.1
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
        
        print('✅ Config updated successfully')
        return True
    except Exception as e:
        print(f'❌ Config update failed: {e}')
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: batch_helper.py <command> [args...]')
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'create_test_urls':
        if len(sys.argv) < 4:
            print('Usage: batch_helper.py create_test_urls <input_file> <output_file> [count]')
            sys.exit(1)
        input_file = sys.argv[2]
        output_file = sys.argv[3]
        count = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        success = create_test_urls(input_file, output_file, count)
        sys.exit(0 if success else 1)
    
    elif command == 'create_test_config':
        if len(sys.argv) < 3:
            print('Usage: batch_helper.py create_test_config <base_url> [url_file] [output_file]')
            sys.exit(1)
        base_url = sys.argv[2]
        url_file = sys.argv[3] if len(sys.argv) > 3 else 'quick_test_urls.txt'
        output_file = sys.argv[4] if len(sys.argv) > 4 else 'quick_test_config.json'
        success = create_test_config(base_url, url_file, output_file)
        sys.exit(0 if success else 1)
    
    elif command == 'update_use_case_config':
        if len(sys.argv) < 3:
            print('Usage: batch_helper.py update_use_case_config <use_case_name>')
            sys.exit(1)
        use_case_name = sys.argv[2]
        success = update_use_case_config(use_case_name)
        sys.exit(0 if success else 1)
    
    else:
        print(f'Unknown command: {command}')
        sys.exit(1)
