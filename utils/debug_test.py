#!/usr/bin/env python3

import requests
from pathlib import Path
import os

# Test basic functionality
url = "http://localhost:1313"
print(f"Testing URL: {url}")

try:
    # Test HTTP request
    response = requests.get(url, timeout=10)
    print(f"✅ HTTP Status: {response.status_code}")
    print(f"✅ Content length: {len(response.text)}")
    
    # Test readabilipy
    try:
        from readabilipy import simple_json_from_html_string
        extracted = simple_json_from_html_string(response.text, use_readability=True)
        content = extracted.get('content', '')
        title = extracted.get('title', '')
        print(f"✅ Readabilipy title: {title}")
        print(f"✅ Readabilipy content length: {len(content)}")
    except Exception as e:
        print(f"❌ Readabilipy error: {e}")
        
    # Test markdown conversion
    try:
        import markdownify
        markdown_content = markdownify.markdownify(content, heading_style="ATX")
        print(f"✅ Markdown content length: {len(markdown_content)}")
    except Exception as e:
        print(f"❌ Markdownify error: {e}")
        
    # Test file creation
    test_dir = Path("output/debug-test")
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test.md"
    
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    file_size = test_file.stat().st_size
    print(f"✅ Created file: {test_file}")
    print(f"✅ File size: {file_size} bytes")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
