#!/usr/bin/env python3
"""
URL Discovery Script for Blueprint API Documentation
Discovers all HTML files in the local UE5.4 Blueprint API documentation
"""

import os
import requests
from pathlib import Path
from urllib.parse import urljoin
import time

def discover_blueprint_urls(docs_path: str, base_url: str = "http://localhost:8081"):
    """
    Discover all HTML files in the Blueprint API documentation directory
    
    Args:
        docs_path: Path to the local documentation directory
        base_url: Base URL of the local HTTP server
    """
    docs_path = Path(docs_path)
    
    if not docs_path.exists():
        print(f"❌ Documentation path not found: {docs_path}")
        print(f"💡 Make sure UE5.4 is installed and the path is correct")
        return []
    
    print(f"🔍 Discovering HTML files in: {docs_path}")
    
    # Find all HTML files
    html_files = list(docs_path.glob("**/*.html"))
    print(f"📊 Found {len(html_files)} HTML files")
    
    if len(html_files) == 0:
        print("⚠️ No HTML files found")
        return []
    
    # Convert file paths to URLs
    urls = []
    for file in html_files:
        # Get relative path from docs directory
        rel_path = file.relative_to(docs_path)
        # Convert Windows path separators to URL separators
        url_path = str(rel_path).replace('\\', '/')
        # Create full URL
        full_url = urljoin(base_url + "/", url_path)
        urls.append(full_url)
    
    # Show sample URLs
    print(f"📄 Sample URLs discovered:")
    for i, url in enumerate(urls[:10]):
        print(f"   {url}")
    
    if len(urls) > 10:
        print(f"   ... and {len(urls) - 10} more URLs")
    
    return urls

def test_server_connection(base_url: str = "http://localhost:8081"):
    """Test if the local HTTP server is running"""
    print(f"🔗 Testing connection to {base_url}...")
    
    try:
        response = requests.get(base_url, timeout=5)
        print(f"✅ Server is accessible (Status: {response.status_code})")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to server at {base_url}")
        print(f"💡 Make sure you started the HTTP server:")
        print(f'   cd "C:\\Program Files\\Epic Games\\UE_5.4\\Engine\\Documentation\\Builds\\BlueprintAPI-HTML"')
        print(f"   python -m http.server 8081")
        return False
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")
        return False

def save_urls_to_file(urls: list, filename: str = "blueprint_api_urls.txt"):
    """Save discovered URLs to a file"""
    if not urls:
        print("⚠️ No URLs to save")
        return None
    
    urls_file = Path(filename)
    with open(urls_file, 'w', encoding='utf-8') as f:
        for url in urls:
            f.write(url + '\n')
    
    print(f"💾 Saved {len(urls)} URLs to: {urls_file}")
    return urls_file

def main():
    print("🎯 Blueprint API URL Discovery")
    print("="*50)
    
    # Configuration
    docs_path = r"C:\Program Files\Epic Games\UE_5.4\Engine\Documentation\Builds\BlueprintAPI-HTML"
    base_url = "http://localhost:8081"
    
    # Step 1: Test server connection
    if not test_server_connection(base_url):
        print("\n❌ Please start the HTTP server first, then run this script again")
        return
    
    # Step 2: Discover URLs
    urls = discover_blueprint_urls(docs_path, base_url)
    
    if not urls:
        print("\n❌ No URLs discovered")
        return
    
    # Step 3: Save URLs to file
    urls_file = save_urls_to_file(urls)
    
    if urls_file:
        print(f"\n✅ URL discovery completed!")
        print(f"📊 Total URLs: {len(urls)}")
        print(f"📄 URLs file: {urls_file}")
        print(f"\n🚀 Next step: Run the document processor")
        print(f"   python doc_processor.py full-pipeline --config config_blueprint_api.json")

if __name__ == "__main__":
    main()
