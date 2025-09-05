#!/usr/bin/env python3
"""
Project Cleanup Script
Removes obsolete scripts that have been consolidated into doc_processor.py
"""

import os
import shutil
from pathlib import Path

def cleanup_project():
    """Remove obsolete files and directories"""
    
    print("🧹 SmolCrawl Project Cleanup")
    print("=" * 50)
    print("Removing obsolete scripts consolidated into doc_processor.py")
    print()
    
    # Files to remove (superseded by unified tool)
    files_to_remove = [
        'complete_extractor.py',          # Merged into doc_processor.py extract
        'merge_unreal_docs.py',           # Merged into doc_processor.py merge  
        'batch_processor.py',             # Merged into doc_processor.py full-pipeline
        'extract_urls.py',                # Utility no longer needed
        'examine_cache.py',               # Specialized utility
        'monitor_progress.py',            # Progress tracking built into unified tool
        'test_manual_crawl.py',           # Development test script
        'test_readability.py',            # Development test script
        'test_http_server.py',            # Development test script
        'test_merge.py',                  # If exists, superseded by test_doc_processor.py
        'crawl_analysis.md',              # Old analysis document
        'SUCCESS_SUMMARY.md',             # Old summary, superseded by UNIFICATION_COMPLETE.md
        'MERGE_SUMMARY.md',               # Old merge summary
        'unreal_urls_discovered.txt',     # Renamed to discovered_urls.txt
    ]
    
    # Directories to remove (test/demo data)
    dirs_to_remove = [
        'test_merge',                     # Demo merge test directory
        '__pycache__',                    # Python cache (will regenerate)
    ]
    
    # Optional files to remove (user decision)
    optional_files = [
        'Demo_Merged_Documentation.md',   # Demo output file
        'migrated_config.json',           # Generated migration config
    ]
    
    removed_count = 0
    kept_count = 0
    
    # Remove obsolete files
    print("📂 Removing obsolete files:")
    for filename in files_to_remove:
        file_path = Path(filename)
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"  ✅ Removed: {filename}")
                removed_count += 1
            except Exception as e:
                print(f"  ❌ Failed to remove {filename}: {e}")
        else:
            print(f"  ⚪ Not found: {filename}")
    
    # Remove obsolete directories
    print(f"\n📁 Removing obsolete directories:")
    for dirname in dirs_to_remove:
        dir_path = Path(dirname)
        if dir_path.exists() and dir_path.is_dir():
            try:
                shutil.rmtree(dir_path)
                print(f"  ✅ Removed directory: {dirname}")
                removed_count += 1
            except Exception as e:
                print(f"  ❌ Failed to remove directory {dirname}: {e}")
        else:
            print(f"  ⚪ Not found: {dirname}")
    
    # Handle optional files
    print(f"\n❓ Optional files (you decide):")
    for filename in optional_files:
        file_path = Path(filename)
        if file_path.exists():
            response = input(f"  Remove {filename}? (y/N): ").lower()
            if response in ['y', 'yes']:
                try:
                    file_path.unlink()
                    print(f"    ✅ Removed: {filename}")
                    removed_count += 1
                except Exception as e:
                    print(f"    ❌ Failed to remove {filename}: {e}")
            else:
                print(f"    ⚪ Kept: {filename}")
                kept_count += 1
        else:
            print(f"  ⚪ Not found: {filename}")
    
    # Show remaining important files
    print(f"\n📋 Key files that remain:")
    important_files = [
        'doc_processor.py',               # Unified tool
        'test_doc_processor.py',          # Test suite
        'migrate_to_doc_processor.py',    # Migration utility
        'DOC_PROCESSOR_README.md',        # Documentation
        'config_unreal.json',             # Configuration
        'config_unreal.yaml',             # YAML configuration
        'doc_processor_config.json',      # Sample configuration
        'UNIFICATION_COMPLETE.md',        # Final summary
        'check_cache.py',                 # Still useful for debugging
        'readabilipy_windows_fix.py',     # Required dependency fix
        'README.md',                      # Project readme
        'LICENSE.md',                     # License
        'pyproject.toml',                 # Project config
    ]
    
    for filename in important_files:
        file_path = Path(filename)
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"  ✅ {filename} ({size:,} bytes)")
            kept_count += 1
        else:
            print(f"  ⚠️ Missing: {filename}")
    
    print(f"\n" + "=" * 50)
    print(f"🎉 Cleanup completed!")
    print(f"📊 Summary:")
    print(f"   • Files removed: {removed_count}")
    print(f"   • Important files kept: {kept_count}")
    print(f"   • Project is now streamlined around doc_processor.py")
    
    print(f"\n🚀 Next steps:")
    print(f"   • Use: python doc_processor.py --help")
    print(f"   • Test: python test_doc_processor.py")
    print(f"   • Read: DOC_PROCESSOR_README.md")

if __name__ == "__main__":
    cleanup_project()
