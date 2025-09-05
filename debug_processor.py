#!/usr/bin/env python3

import sys
import os
sys.path.append('use-cases/document-processing')

from doc_processor import DocumentProcessor, ProcessingConfig

# Test the config loading
processor = DocumentProcessor.from_config_file('use-cases/localhost-1313/test_config.json')
config = processor.config
print(f"Config loaded:")
print(f"  base_url: {config.base_url}")
print(f"  output_dir: {config.output_dir}")
print(f"  url_list_file: {config.url_list_file}")
print(f"Processor output_dir: {processor.output_dir}")
print(f"Processor output_dir absolute: {processor.output_dir.absolute()}")
print(f"Processor output_dir exists: {processor.output_dir.exists()}")

# Test single URL processing
test_url = "http://localhost:1313"
print(f"\nTesting single URL: {test_url}")

try:
    result = processor.process_single_url(test_url)
    print(f"Result: {result}")
    
    if result['success']:
        print(f"✅ File created: {result['file_path']}")
        if os.path.exists(result['file_path']):
            file_size = os.path.getsize(result['file_path'])
            print(f"✅ File size: {file_size} bytes")
        else:
            print(f"❌ File not found: {result['file_path']}")
    else:
        print(f"❌ Error: {result['error']}")
        
except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()
