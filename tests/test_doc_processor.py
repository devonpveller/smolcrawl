#!/usr/bin/env python3
"""
Test script for the Universal Document Processor
Validates configuration and runs basic functionality tests
"""

import json
import sys
from pathlib import Path
from doc_processor import DocumentProcessor, ProcessingConfig

def test_config_loading():
    """Test configuration file loading"""
    print("🧪 Testing configuration loading...")
    
    # Test JSON config
    try:
        processor = DocumentProcessor.from_config_file('config_unreal.json')
        print("  ✅ JSON config loaded successfully")
        print(f"     Base URL: {processor.config.base_url}")
        print(f"     Categories: {processor.config.categories}")
    except Exception as e:
        print(f"  ❌ JSON config failed: {e}")
    
    # Test YAML config
    try:
        processor = DocumentProcessor.from_config_file('config_unreal.yaml')
        print("  ✅ YAML config loaded successfully")
    except Exception as e:
        print(f"  ❌ YAML config failed: {e}")

def test_url_processing():
    """Test URL processing functions"""
    print("\n🧪 Testing URL processing...")
    
    config = ProcessingConfig(base_url="http://localhost:8080")
    processor = DocumentProcessor(config)
    
    # Test URL categorization
    test_urls = [
        "http://localhost:8080/API/Runtime/Core/HAL/class_f_platform_file_manager.html",
        "http://localhost:8080/API/Editor/UnrealEd/class_u_editor_engine.html",
        "http://localhost:8080/API/Plugins/VirtualProduction/class_a_virtual_production_actor.html",
        "http://localhost:8080/API/SomeOther/Unknown/class_test.html"
    ]
    
    for url in test_urls:
        category = processor.categorize_url(url)
        filename = processor.clean_filename(url)
        print(f"  📄 {url}")
        print(f"     Category: {category}")
        print(f"     Filename: {filename}")

def test_file_discovery():
    """Test markdown file discovery"""
    print("\n🧪 Testing file discovery...")
    
    config = ProcessingConfig(output_dir="output/extracted_docs")
    processor = DocumentProcessor(config)
    
    # Check if output directory exists
    if processor.output_dir.exists():
        files = processor.get_all_markdown_files()
        print(f"  📊 Found {len(files)} markdown files")
        
        # Show category breakdown
        category_counts = {}
        for category, _ in files:
            category_counts[category] = category_counts.get(category, 0) + 1
        
        for category, count in category_counts.items():
            print(f"     {category}: {count} files")
    else:
        print(f"  ⚠️ Output directory not found: {processor.output_dir}")

def test_sample_extraction():
    """Test extraction on a few sample URLs"""
    print("\n🧪 Testing sample extraction...")
    
    # Only test if discovered_urls.txt exists
    urls_file = Path("discovered_urls.txt")
    if not urls_file.exists():
        print("  ⚠️ No discovered_urls.txt found, skipping extraction test")
        return
    
    # Read first 3 URLs for testing
    with open(urls_file, 'r') as f:
        test_urls = [line.strip() for line in f.readlines()[:3] if line.strip()]
    
    if not test_urls:
        print("  ⚠️ No URLs found in file")
        return
    
    config = ProcessingConfig(
        base_url="http://localhost:8080",
        output_dir="output/test_docs",
        max_workers=2
    )
    processor = DocumentProcessor(config)
    
    print(f"  🚀 Testing extraction of {len(test_urls)} URLs...")
    
    try:
        result = processor.extract_documents(test_urls)
        print(f"  ✅ Test extraction completed")
        print(f"     Successful: {result['summary']['successful']}")
        print(f"     Failed: {result['summary']['failed']}")
    except Exception as e:
        print(f"  ❌ Test extraction failed: {e}")

def main():
    print("🧪 Universal Document Processor - Test Suite")
    print("=" * 50)
    
    test_config_loading()
    test_url_processing()
    test_file_discovery()
    
    # Ask before running extraction test
    response = input("\n❓ Run sample extraction test? (y/N): ")
    if response.lower() in ['y', 'yes']:
        test_sample_extraction()
    
    print("\n✅ Test suite completed!")

if __name__ == "__main__":
    main()
