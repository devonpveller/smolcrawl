#!/usr/bin/env python3
"""
Blueprint API Processing Monitor
Monitor the progress of the Blueprint API documentation processing
"""

import time
import os
from pathlib import Path

def check_processing_progress():
    """Check and display current processing progress"""
    print("Blueprint API Processing Monitor")
    print("=" * 50)
    
    # Check URLs file
    urls_file = Path("blueprint_api_urls.txt")
    if urls_file.exists():
        with open(urls_file, 'r') as f:
            total_urls = sum(1 for line in f if line.strip())
        print(f"Total URLs to process: {total_urls:,}")
    else:
        print("URLs file not found")
        return
    
    # Check output directory
    output_dir = Path("output/blueprint_api_docs")
    if output_dir.exists():
        # Count processed files
        md_files = list(output_dir.glob("**/*.md"))
        processed_count = len(md_files)
        
        print(f"Files processed: {processed_count:,}")
        print(f"Progress: {(processed_count/total_urls)*100:.1f}%")
        
        if processed_count > 0:
            # Calculate size
            total_size = sum(f.stat().st_size for f in md_files)
            size_mb = total_size / (1024 * 1024)
            print(f"Total size: {size_mb:.1f} MB")
            
            # Show category breakdown
            categories = {}
            for file in md_files:
                category = file.parent.name
                categories[category] = categories.get(category, 0) + 1
            
            print("\nFiles by category:")
            for category, count in sorted(categories.items()):
                print(f"  {category}: {count:,} files")
        
        # Estimate completion time if processing
        if processed_count > 0 and processed_count < total_urls:
            remaining = total_urls - processed_count
            print(f"\nRemaining: {remaining:,} files")
            
            # Try to estimate rate based on recent processing
            print("Processing is active...")
    else:
        print("Output directory not found - processing may not have started yet")
    
    # Check for merged file
    merged_file = Path("UE54_Blueprint_API_Complete_Documentation.md")
    if merged_file.exists():
        size_mb = merged_file.stat().st_size / (1024 * 1024)
        print(f"\nMerged documentation: {merged_file} ({size_mb:.1f} MB)")
        print("Processing appears to be COMPLETE!")
    else:
        print("\nMerged documentation not found - processing still in progress")

def main():
    """Main monitoring function"""
    try:
        check_processing_progress()
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
