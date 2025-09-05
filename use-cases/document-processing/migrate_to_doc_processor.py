#!/usr/bin/env python3
"""
Migration utility for transitioning from specialized scripts to doc_processor.py
Generates equivalent commands and configurations
"""

import json
import argparse
from pathlib import Path

def analyze_complete_extractor():
    """Analyze complete_extractor.py usage and suggest migration"""
    print("🔍 Analyzing complete_extractor.py...")
    
    # Check if file exists
    extractor_file = Path("complete_extractor.py")
    if not extractor_file.exists():
        print("  ⚠️ complete_extractor.py not found")
        return
    
    print("  📝 Migration suggestions:")
    print("     Old command: python complete_extractor.py")
    print("     New command: python doc_processor.py extract --config config.json")
    print()
    print("  📋 Configuration mapping:")
    print("     CompleteUnrealExtractor.__init__ parameters → config.json:")
    print("       base_url → base_url")
    print("       output_dir → output_dir") 
    print("       max_workers → max_workers")
    print("       discovered_urls.txt → url_list_file")

def analyze_merge_unreal_docs():
    """Analyze merge_unreal_docs.py usage and suggest migration"""
    print("\n🔍 Analyzing merge_unreal_docs.py...")
    
    merge_file = Path("merge_unreal_docs.py")
    if not merge_file.exists():
        print("  ⚠️ merge_unreal_docs.py not found")
        return
    
    print("  📝 Migration suggestions:")
    print("     Old command: python merge_unreal_docs.py")
    print("     New command: python doc_processor.py merge --config config.json")
    print()
    print("  📋 Configuration mapping:")
    print("     CATEGORY_ORDER → category_order")
    print("     get_all_markdown_files() → automatic file discovery")
    print("     create_table_of_contents() → include_toc: true")

def analyze_batch_processor():
    """Analyze batch_processor.py usage and suggest migration"""
    print("\n🔍 Analyzing batch_processor.py...")
    
    batch_file = Path("batch_processor.py")
    if not batch_file.exists():
        print("  ⚠️ batch_processor.py not found")
        return
    
    print("  📝 Migration suggestions:")
    print("     Old command: python batch_processor.py")
    print("     New command: python doc_processor.py full-pipeline --config config.json")
    print()
    print("  📋 Configuration mapping:")
    print("     UnrealDocProcessor.__init__ parameters → config.json:")
    print("       base_url → base_url")
    print("       output_dir → output_dir")
    print("       process_page() → integrated in doc_processor")

def create_migration_config():
    """Create a configuration file based on existing script parameters"""
    print("\n📝 Creating migration configuration...")
    
    # Try to extract parameters from existing scripts
    config = {
        "base_url": "http://localhost:8080",
        "url_list_file": "discovered_urls.txt",
        "max_workers": 6,
        "timeout": 15,
        "output_dir": "output/extracted_docs",
        "merge_output": "merged_documentation.md",
        "categories": ["Runtime", "Editor", "Plugins", "Other"],
        "category_order": ["Runtime", "Editor", "Plugins", "Other"],
        "clean_content": True,
        "add_metadata": True,
        "use_readability": True,
        "convert_to_markdown": True,
        "include_toc": True
    }
    
    # Check for existing settings
    urls_file = Path("discovered_urls.txt")
    if urls_file.exists():
        print(f"  ✅ Found URL list: {urls_file}")
        config["url_list_file"] = str(urls_file)
    
    output_dir = Path("output/extracted_docs")
    if output_dir.exists():
        print(f"  ✅ Found output directory: {output_dir}")
        config["output_dir"] = str(output_dir)
    
    # Write configuration file
    config_file = Path("migrated_config.json")
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"  📄 Created configuration: {config_file}")
    return config_file

def generate_migration_commands():
    """Generate equivalent commands for common operations"""
    print("\n📋 Migration Command Reference:")
    print("=" * 50)
    
    commands = [
        {
            "old": "python complete_extractor.py",
            "new": "python doc_processor.py extract --config migrated_config.json",
            "description": "Extract all documents with multithreading"
        },
        {
            "old": "python merge_unreal_docs.py", 
            "new": "python doc_processor.py merge --config migrated_config.json",
            "description": "Merge extracted documents into single file"
        },
        {
            "old": "python batch_processor.py",
            "new": "python doc_processor.py full-pipeline --config migrated_config.json", 
            "description": "Run complete extraction and merge pipeline"
        },
        {
            "old": "Manual URL discovery → extraction → merging",
            "new": "python doc_processor.py full-pipeline --config migrated_config.json",
            "description": "Automated end-to-end processing"
        }
    ]
    
    for cmd in commands:
        print(f"📌 {cmd['description']}")
        print(f"   Old: {cmd['old']}")
        print(f"   New: {cmd['new']}")
        print()

def check_dependencies():
    """Check if all required dependencies are available"""
    print("🔍 Checking dependencies...")
    
    dependencies = [
        ("requests", "HTTP requests"),
        ("readabilipy", "Content extraction"),
        ("markdownify", "HTML to Markdown conversion"),
        ("pyyaml", "YAML configuration support")
    ]
    
    missing = []
    for module, description in dependencies:
        try:
            __import__(module)
            print(f"  ✅ {module} - {description}")
        except ImportError:
            print(f"  ❌ {module} - {description} (MISSING)")
            missing.append(module)
    
    if missing:
        print(f"\n📦 Install missing dependencies:")
        print(f"   pip install {' '.join(missing)}")

def main():
    parser = argparse.ArgumentParser(description="Migration utility for doc_processor.py")
    parser.add_argument('--create-config', action='store_true', help='Create migration configuration')
    parser.add_argument('--analyze', action='store_true', help='Analyze existing scripts')
    parser.add_argument('--commands', action='store_true', help='Show command migration reference')
    parser.add_argument('--check-deps', action='store_true', help='Check dependencies')
    
    args = parser.parse_args()
    
    if not any([args.create_config, args.analyze, args.commands, args.check_deps]):
        # Run all checks by default
        args.analyze = True
        args.create_config = True
        args.commands = True
        args.check_deps = True
    
    print("🚀 Document Processor Migration Utility")
    print("=" * 50)
    
    if args.check_deps:
        check_dependencies()
    
    if args.analyze:
        analyze_complete_extractor()
        analyze_merge_unreal_docs()
        analyze_batch_processor()
    
    if args.create_config:
        config_file = create_migration_config()
    
    if args.commands:
        generate_migration_commands()
    
    print("✅ Migration analysis completed!")
    print("\n🎯 Next steps:")
    print("   1. Review the generated migrated_config.json")
    print("   2. Test with: python test_doc_processor.py")
    print("   3. Run extraction: python doc_processor.py full-pipeline --config migrated_config.json")

if __name__ == "__main__":
    main()
