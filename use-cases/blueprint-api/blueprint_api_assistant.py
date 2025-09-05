#!/usr/bin/env python3
"""
Blueprint API Processing Assistant
Interactive script to help process UE5.4 Blueprint API documentation
"""

import os
import sys
import time
import subprocess
import requests
from pathlib import Path

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"🎯 {title}")
    print("="*60)

def print_step(step_num, title):
    """Print a formatted step"""
    print(f"\n📋 STEP {step_num}: {title}")
    print("-" * 40)

def check_python():
    """Check if Python is available"""
    try:
        result = subprocess.run([sys.executable, "--version"], 
                              capture_output=True, text=True)
        python_version = result.stdout.strip()
        print(f"✅ Python found: {python_version}")
        return True
    except Exception as e:
        print(f"❌ Python check failed: {e}")
        return False

def check_ue54_path():
    """Check if UE5.4 Blueprint API documentation exists"""
    ue54_path = Path(r"C:\Program Files\Epic Games\UE_5.4\Engine\Documentation\Builds\BlueprintAPI-HTML")
    
    if ue54_path.exists():
        print(f"✅ Found UE5.4 Blueprint API documentation at: {ue54_path}")
        
        # Count HTML files
        html_files = list(ue54_path.glob("**/*.html"))
        print(f"📊 Found {len(html_files)} HTML files to process")
        
        if len(html_files) > 0:
            print("📄 Sample files:")
            for i, file in enumerate(html_files[:3]):
                rel_path = file.relative_to(ue54_path)
                print(f"   {rel_path}")
                if i == 2 and len(html_files) > 3:
                    print(f"   ... and {len(html_files) - 3} more files")
        
        return True, ue54_path, len(html_files)
    else:
        print(f"❌ UE5.4 Blueprint API documentation not found at: {ue54_path}")
        print("💡 Please verify:")
        print("   - Unreal Engine 5.4 is installed")
        print("   - Blueprint API documentation is installed")
        print("   - The installation path is correct")
        return False, None, 0

def start_http_server(docs_path):
    """Guide user to start HTTP server"""
    print(f"🚀 Starting HTTP server for Blueprint API documentation...")
    print(f"📂 Documentation path: {docs_path}")
    print()
    print("Please open a NEW command prompt window and run these commands:")
    print(f'cd "{docs_path}"')
    print("python -m http.server 8081")
    print()
    print("⚠️ IMPORTANT: Keep that command prompt window open during processing!")
    print()
    
    input("Press Enter when you have started the HTTP server...")
    
    # Test server connection
    print("\n🔗 Testing server connection...")
    for attempt in range(5):
        try:
            response = requests.get("http://localhost:8081", timeout=3)
            print(f"✅ Server is running! (Status: {response.status_code})")
            return True
        except requests.exceptions.ConnectionError:
            print(f"⏳ Attempt {attempt + 1}/5: Server not ready yet...")
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ Connection test error: {e}")
            time.sleep(2)
    
    print("❌ Could not connect to HTTP server")
    print("Please make sure the server is running and try again")
    return False

def discover_and_process():
    """Run URL discovery and document processing"""
    print("🔍 Starting URL discovery...")
    
    # Run URL discovery
    try:
        result = subprocess.run([sys.executable, "discover_blueprint_urls.py"], 
                              capture_output=True, text=True)
        print("URL Discovery Output:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        if result.returncode != 0:
            print("❌ URL discovery failed")
            return False
        
        # Check if URLs file was created
        urls_file = Path("blueprint_api_urls.txt")
        if not urls_file.exists():
            print("❌ URLs file not created")
            return False
        
        # Count URLs
        with open(urls_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        print(f"📊 Discovered {len(urls)} URLs for processing")
        
    except Exception as e:
        print(f"❌ URL discovery error: {e}")
        return False
    
    print("\n🚀 Starting document processing...")
    print("This may take several minutes depending on the number of files...")
    
    # Run document processing
    try:
        result = subprocess.run([
            sys.executable, "doc_processor.py", "full-pipeline", 
            "--config", "config_blueprint_api.json"
        ], capture_output=True, text=True)
        
        print("Processing Output:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ Document processing completed successfully!")
            return True
        else:
            print("❌ Document processing failed")
            return False
            
    except Exception as e:
        print(f"❌ Processing error: {e}")
        return False

def check_results():
    """Check and display processing results"""
    print("📊 Checking processing results...")
    
    # Check output directory
    output_dir = Path("output/blueprint_api_docs")
    if output_dir.exists():
        md_files = list(output_dir.glob("**/*.md"))
        print(f"✅ Created {len(md_files)} individual markdown files")
        
        # Show category breakdown
        categories = {}
        for file in md_files:
            category = file.parent.name
            categories[category] = categories.get(category, 0) + 1
        
        print("📂 Files by category:")
        for category, count in categories.items():
            print(f"   {category}: {count} files")
    else:
        print("⚠️ Output directory not found")
    
    # Check merged file
    merged_file = Path("UE54_Blueprint_API_Complete_Documentation.md")
    if merged_file.exists():
        size_mb = merged_file.stat().st_size / (1024 * 1024)
        print(f"✅ Created merged documentation: {merged_file} ({size_mb:.1f} MB)")
    else:
        print("⚠️ Merged documentation file not found")
    
    return output_dir.exists() or merged_file.exists()

def main():
    """Main processing function"""
    print_header("UE5.4 Blueprint API Documentation Processor")
    
    print("This interactive script will help you process your local UE5.4 Blueprint API")
    print("documentation and convert it to clean, organized markdown files.")
    print()
    
    # Step 1: Check prerequisites
    print_step(1, "Checking Prerequisites")
    
    if not check_python():
        return False
    
    found_docs, docs_path, file_count = check_ue54_path()
    if not found_docs:
        return False
    
    if file_count == 0:
        print("❌ No HTML files found to process")
        return False
    
    # Step 2: Start HTTP server
    print_step(2, "Starting HTTP Server")
    
    if not start_http_server(docs_path):
        return False
    
    # Step 3: Process documentation
    print_step(3, "Processing Documentation")
    
    if not discover_and_process():
        return False
    
    # Step 4: Check results
    print_step(4, "Checking Results")
    
    success = check_results()
    
    # Final summary
    print_header("Processing Complete!")
    
    if success:
        print("🎉 SUCCESS: Blueprint API documentation has been processed!")
        print()
        print("📁 Results locations:")
        print("   • Individual files: output/blueprint_api_docs/")
        print("   • Merged document: UE54_Blueprint_API_Complete_Documentation.md")
        print()
        print("💡 You can now:")
        print("   • Browse individual markdown files by category")
        print("   • Use the merged document for comprehensive reference")
        print("   • Share or integrate the markdown files in your projects")
        
        # Stop server instruction
        print()
        print("🛑 Don't forget to stop the HTTP server:")
        print("   Go to the command prompt window with the server and press Ctrl+C")
        
        return True
    else:
        print("❌ FAILED: Processing encountered errors")
        print("💡 Check the output above for specific error messages")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
