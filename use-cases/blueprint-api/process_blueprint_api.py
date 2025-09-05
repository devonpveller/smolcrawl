#!/usr/bin/env python3
"""
Blueprint API Documentation Processor
Extract and convert local Unreal Engine 5.4 Blueprint API HTML documentation to markdown
"""

import os
import http.server
import socketserver
import threading
import time
import json
from pathlib import Path
from urllib.parse import urljoin
import requests
from doc_processor import DocumentProcessor, ProcessingConfig

class BlueprintAPIProcessor:
    """Specialized processor for UE5.4 Blueprint API documentation"""
    
    def __init__(self, local_docs_path: str):
        self.local_docs_path = Path(local_docs_path)
        self.server_port = 8081
        self.base_url = f"http://localhost:{self.server_port}"
        self.server_thread = None
        self.httpd = None
        
    def verify_local_path(self):
        """Verify the local documentation path exists"""
        if not self.local_docs_path.exists():
            raise FileNotFoundError(f"Documentation path not found: {self.local_docs_path}")
        
        print(f"✅ Found local documentation at: {self.local_docs_path}")
        
        # Check for common Blueprint API files
        html_files = list(self.local_docs_path.glob("**/*.html"))
        print(f"📊 Found {len(html_files)} HTML files")
        
        if len(html_files) == 0:
            print("⚠️ No HTML files found in the specified directory")
            return False
        
        # Show some sample files
        print("📄 Sample files found:")
        for i, file in enumerate(html_files[:5]):
            rel_path = file.relative_to(self.local_docs_path)
            print(f"   {rel_path}")
        
        if len(html_files) > 5:
            print(f"   ... and {len(html_files) - 5} more files")
        
        return True
    
    def start_local_server(self):
        """Start local HTTP server to serve the documentation files"""
        print(f"🚀 Starting local HTTP server on port {self.server_port}...")
        
        os.chdir(self.local_docs_path)
        
        handler = http.server.SimpleHTTPRequestHandler
        self.httpd = socketserver.TCPServer(("", self.server_port), handler)
        
        # Start server in background thread
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        
        # Wait a moment for server to start
        time.sleep(2)
        
        # Test server is working
        try:
            response = requests.get(self.base_url, timeout=5)
            print(f"✅ Server is running at {self.base_url}")
            return True
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
    
    def stop_local_server(self):
        """Stop the local HTTP server"""
        if self.httpd:
            self.httpd.shutdown()
            print("🛑 Local HTTP server stopped")
    
    def discover_urls(self):
        """Discover all HTML URLs in the local documentation"""
        print("🔍 Discovering HTML files...")
        
        html_files = list(self.local_docs_path.glob("**/*.html"))
        urls = []
        
        for file in html_files:
            # Convert file path to URL path
            rel_path = file.relative_to(self.local_docs_path)
            url_path = str(rel_path).replace('\\', '/')  # Convert Windows paths to URL paths
            full_url = urljoin(self.base_url + "/", url_path)
            urls.append(full_url)
        
        print(f"📊 Discovered {len(urls)} URLs")
        
        # Save URLs to file for processing
        urls_file = Path("blueprint_api_urls.txt")
        with open(urls_file, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(url + '\n')
        
        print(f"💾 URLs saved to: {urls_file}")
        return urls_file, urls
    
    def create_blueprint_config(self, urls_file: str):
        """Create configuration for Blueprint API processing"""
        config = {
            "base_url": self.base_url,
            "url_list_file": str(urls_file),
            "max_workers": 8,
            "timeout": 30,
            "delay_between_requests": 0.05,  # Fast for local server
            "output_dir": "output/blueprint_api_docs",
            "merge_output": "UE54_Blueprint_API_Complete_Documentation.md",
            "categories": [
                "Classes",
                "Functions", 
                "Components",
                "Interfaces",
                "Enums",
                "Structs",
                "Other"
            ],
            "category_order": [
                "Classes",
                "Functions",
                "Components", 
                "Interfaces",
                "Enums",
                "Structs",
                "Other"
            ],
            "clean_content": True,
            "add_metadata": True,
            "use_readability": True,
            "convert_to_markdown": True,
            "include_toc": True
        }
        
        config_file = Path("config_blueprint_api.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        print(f"⚙️ Configuration created: {config_file}")
        return config_file
    
    def process_documentation(self):
        """Complete process: serve files, discover URLs, and extract documentation"""
        try:
            # Step 1: Verify local path
            if not self.verify_local_path():
                return False
            
            # Step 2: Start local server
            if not self.start_local_server():
                return False
            
            # Step 3: Discover URLs
            urls_file, urls = self.discover_urls()
            
            # Step 4: Create configuration
            config_file = self.create_blueprint_config(urls_file)
            
            # Step 5: Process with unified tool
            print("\n" + "="*60)
            print("🚀 Starting Blueprint API documentation processing...")
            print("="*60)
            
            # Create processor and run
            processor = DocumentProcessor.from_config_file(str(config_file))
            result = processor.run_full_pipeline()
            
            return result['success']
            
        except Exception as e:
            print(f"❌ Error during processing: {e}")
            return False
        finally:
            # Always stop the server
            self.stop_local_server()

def main():
    """Main function to process Blueprint API documentation"""
    print("🎯 Unreal Engine 5.4 Blueprint API Documentation Processor")
    print("="*70)
    
    # Default path - can be modified
    docs_path = r"C:\Program Files\Epic Games\UE_5.4\Engine\Documentation\Builds\BlueprintAPI-HTML"
    
    # Allow user to specify different path
    import sys
    if len(sys.argv) > 1:
        docs_path = sys.argv[1]
    
    print(f"📂 Processing documentation from: {docs_path}")
    
    try:
        processor = BlueprintAPIProcessor(docs_path)
        success = processor.process_documentation()
        
        if success:
            print("\n" + "="*70)
            print("🎉 Blueprint API documentation processing completed successfully!")
            print("📁 Check output/blueprint_api_docs/ for extracted files")
            print("📄 Check UE54_Blueprint_API_Complete_Documentation.md for merged output")
        else:
            print("\n❌ Documentation processing failed")
            
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        print("💡 Make sure Unreal Engine 5.4 is installed and the path is correct")
        print("💡 You can also specify a custom path: python process_blueprint_api.py \"C:\\Your\\Path\"")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
