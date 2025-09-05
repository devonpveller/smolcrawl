#!/usr/bin/env python3
"""
Universal Document Processing Tool
A unified, configurable tool for extracting, processing, and merging web documentation.

This tool combines the functionality of:
- complete_extractor.py
- batch_processor.py  
- merge_unreal_docs.py
- URL discovery and analysis

Usage:
    python doc_processor.py extract --config config.json
    python doc_processor.py merge --input-dir output/docs --output merged_docs.md
    python doc_processor.py full-pipeline --config config.json
"""

import argparse
import json
import requests
import os
import time
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import List, Tuple, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dataclasses import dataclass, asdict
import yaml

# Import dependencies with fallback handling
try:
    from readabilipy import simple_json_from_html_string
    import readabilipy_windows_fix  # Windows compatibility fix
except ImportError:
    print("Warning: readabilipy not available. Install with: pip install readabilipy")
    simple_json_from_html_string = None

try:
    import markdownify
except ImportError:
    print("Warning: markdownify not available. Install with: pip install markdownify")
    markdownify = None

@dataclass
class ProcessingConfig:
    """Configuration for document processing"""
    # Source settings
    base_url: str = "http://localhost:8080"
    url_list_file: Optional[str] = None
    start_urls: Optional[List[str]] = None
    
    # Processing settings
    max_workers: int = 6
    max_retries: int = 3
    timeout: int = 15
    delay_between_requests: float = 0.1
    
    # Output settings
    output_dir: str = "output/extracted_docs"
    merge_output: str = "merged_documentation.md"
    
    # Content settings 
    categories: List[str] = None
    category_order: List[str] = None
    clean_content: bool = True
    add_metadata: bool = True
    
    # Extraction settings
    use_readability: bool = True
    convert_to_markdown: bool = True
    include_toc: bool = True
    
    def __post_init__(self):
        if self.categories is None:
            self.categories = ['Other', 'Runtime', 'Editor', 'Plugins']
        if self.category_order is None:
            self.category_order = self.categories.copy()

class DocumentProcessor:
    """Universal document processing and merging tool"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Thread-safe counters
        self.lock = threading.Lock()
        self.processed_count = 0
        self.failed_count = 0
        self.total_size = 0
        self.results = []
        
    @classmethod
    def from_config_file(cls, config_path: str) -> 'DocumentProcessor':
        """Create processor from config file (JSON or YAML)"""
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.suffix.lower() in ['.yml', '.yaml']:
                config_data = yaml.safe_load(f)
            else:
                config_data = json.load(f)
        
        config = ProcessingConfig(**config_data)
        return cls(config)
    
    def clean_filename(self, url: str) -> str:
        """Convert URL to safe filename"""
        clean = url.replace(self.config.base_url, '').strip('/')
        clean = clean.replace('/', '_').replace(':', '').replace('?', '_').replace('#', '_')
        clean = re.sub(r'[<>:"|*]', '', clean)  # Remove Windows-unsafe chars
        
        # Handle very long filenames
        if len(clean) > 200:
            clean = clean[:200] + "_truncated"
        return clean + '.md'
    
    def categorize_url(self, url: str) -> str:
        """Determine the category/module from URL"""
        parts = url.replace(self.config.base_url, '').strip('/').split('/')
        
        # Try to match against known categories
        for part in parts:
            if part in self.config.categories:
                return part
        
        # Default category detection logic
        if len(parts) >= 3:
            potential_category = parts[2]
            if potential_category.title() in self.config.categories:
                return potential_category.title()
        
        return "Other"
    
    def process_single_url(self, url: str) -> Dict[str, Any]:
        """Process a single URL and extract content"""
        result = {
            'url': url,
            'success': False,
            'error': None,
            'file_path': None,
            'category': self.categorize_url(url),
            'size': 0,
            'title': None
        }
        
        try:
            # Fetch content
            response = requests.get(url, timeout=self.config.timeout)
            response.raise_for_status()
            
            # Extract readable content
            if simple_json_from_html_string:
                extracted = simple_json_from_html_string(
                    response.text, 
                    use_readability=self.config.use_readability
                )
                content = extracted.get('content', '')
                title = extracted.get('title', '')
            else:
                content = response.text
                title = self.extract_title_from_html(response.text)
            
            if not content.strip():
                result['error'] = "No content extracted"
                return result
            
            # Convert to markdown if requested
            if self.config.convert_to_markdown and markdownify:
                content = markdownify.markdownify(content, heading_style="ATX")
            
            # Add metadata if requested
            if self.config.add_metadata:
                metadata = self.create_metadata(url, title, result['category'])
                content = metadata + "\n\n" + content
            
            # Clean content if requested
            if self.config.clean_content:
                content = self.clean_content(content)
            
            # Create category directory
            category_dir = self.output_dir / result['category']
            category_dir.mkdir(exist_ok=True)
            
            # Save to file
            filename = self.clean_filename(url)
            file_path = category_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            result.update({
                'success': True,
                'file_path': str(file_path),
                'size': len(content),
                'title': title
            })
            
            # Small delay to be respectful
            if self.config.delay_between_requests > 0:
                time.sleep(self.config.delay_between_requests)
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def extract_title_from_html(self, html: str) -> str:
        """Extract title from HTML content"""
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
        return "Untitled"
    
    def create_metadata(self, url: str, title: str, category: str) -> str:
        """Create metadata header for document"""
        metadata = [
            f"# {title}",
            "",
            f"**Source:** {url}",
            f"**Category:** {category}",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---"
        ]
        return "\n".join(metadata)
    
    def clean_content(self, content: str) -> str:
        """Clean and standardize content"""
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        
        # Remove common HTML artifacts
        content = re.sub(r'&nbsp;', ' ', content)
        content = re.sub(r'&amp;', '&', content)
        content = re.sub(r'&lt;', '<', content)
        content = re.sub(r'&gt;', '>', content)
        
        return content.strip()
    
    def load_urls_from_file(self, file_path: str) -> List[str]:
        """Load URLs from a text file"""
        urls = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
        return urls
    
    def extract_documents(self, urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract documents from URLs with multi-threading"""
        if urls is None:
            if self.config.url_list_file:
                urls = self.load_urls_from_file(self.config.url_list_file)
            elif self.config.start_urls:
                urls = self.config.start_urls
            else:
                raise ValueError("No URLs provided. Set url_list_file, start_urls, or pass urls parameter.")
        
        print(f"🚀 Starting extraction of {len(urls)} URLs")
        print(f"📁 Output directory: {self.output_dir}")
        print(f"🔧 Using {self.config.max_workers} worker threads")
        print("=" * 80)
        
        start_time = time.time()
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(self.process_single_url, url): url 
                for url in urls
            }
            
            # Process completed tasks
            for future in as_completed(future_to_url):
                result = future.result()
                results.append(result)
                
                # Update counters
                with self.lock:
                    if result['success']:
                        self.processed_count += 1
                        self.total_size += result['size']
                    else:
                        self.failed_count += 1
                
                # Progress update
                total_completed = self.processed_count + self.failed_count
                if total_completed % 10 == 0:
                    progress = (total_completed / len(urls)) * 100
                    elapsed = time.time() - start_time
                    rate = total_completed / elapsed if elapsed > 0 else 0
                    eta = (len(urls) - total_completed) / rate if rate > 0 else 0
                    
                    size_mb = self.total_size / (1024 * 1024)
                    print(f"📊 Progress: {total_completed:4d}/{len(urls)} ({progress:5.1f}%) | "
                          f"✅ {self.processed_count:4d} | ❌ {self.failed_count:2d} | "
                          f"📄 {size_mb:5.1f}MB | ⏱️ {elapsed:6.0f}s | "
                          f"ETA: {eta:4.0f}s | Rate: {rate:4.1f}/s")
        
        # Final summary
        elapsed = time.time() - start_time
        print("=" * 80)
        print(f"📊 EXTRACTION SUMMARY")
        print("=" * 80)
        print(f"✅ Successfully processed: {self.processed_count:,}")
        print(f"❌ Failed: {self.failed_count}")
        print(f"📊 Success rate: {(self.processed_count/len(urls)*100):.1f}%")
        print(f"⏱️ Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"🏃 Processing rate: {len(urls)/elapsed:.1f} URLs/second")
        print(f"📄 Total content: {self.total_size/(1024*1024):.1f} MB")
        print(f"📁 Output directory: {self.output_dir}")
        
        return {
            'results': results,
            'summary': {
                'total_urls': len(urls),
                'successful': self.processed_count,
                'failed': self.failed_count,
                'success_rate': self.processed_count / len(urls) * 100,
                'total_time': elapsed,
                'total_size_mb': self.total_size / (1024 * 1024),
                'output_directory': str(self.output_dir)
            }
        }
    
    def get_all_markdown_files(self, input_dir: Optional[Path] = None) -> List[Tuple[str, Path]]:
        """Find all markdown files organized by category"""
        if input_dir is None:
            input_dir = self.output_dir
        
        all_files = []
        
        for category in self.config.category_order:
            category_path = input_dir / category
            if category_path.exists():
                print(f"📂 Found {category} directory...")
                md_files = list(category_path.glob("*.md"))
                md_files.sort()
                for file_path in md_files:
                    all_files.append((category, file_path))
        
        # Also check for files directly in input directory
        direct_files = [f for f in input_dir.glob("*.md") if f.is_file()]
        for file_path in direct_files:
            all_files.append(("Other", file_path))
        
        return all_files
    
    def create_table_of_contents(self, files: List[Tuple[str, Path]], title: str = "Documentation") -> str:
        """Create comprehensive table of contents"""
        toc = [f"# {title}", ""]
        toc.append("*Complete documentation generated from web sources*")
        toc.append("")
        toc.append("## Table of Contents")
        toc.append("")
        
        # Count files per category
        category_counts = {}
        for category, _ in files:
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Generate TOC with counts
        for category in self.config.category_order:
            if category in category_counts:
                count = category_counts[category]
                toc.append(f"- **{category}** ({count} files)")
        
        toc.append("")
        toc.append("---")
        toc.append("")
        
        return "\n".join(toc)
    
    def clean_markdown_content(self, content: str, file_path: Path) -> str:
        """Clean and standardize markdown content"""
        if not self.config.clean_content:
            return content
        
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        content = content.strip()
        
        # Add source comment
        source_comment = f"<!-- Source: {file_path.name} -->\n\n"
        content = source_comment + content
        
        return content
    
    def merge_documents(self, input_dir: Optional[Path] = None, output_file: Optional[str] = None) -> str:
        """Merge all markdown files into a single document"""
        if input_dir is None:
            input_dir = self.output_dir
        if output_file is None:
            output_file = self.config.merge_output
        
        input_dir = Path(input_dir)
        output_path = Path(output_file)
        
        print(f"🔀 Starting merge from: {input_dir}")
        print(f"📄 Output will be written to: {output_path}")
        
        # Get all markdown files
        all_files = self.get_all_markdown_files(input_dir)
        
        if not all_files:
            print("❌ No markdown files found!")
            return ""
        
        print(f"📊 Found {len(all_files)} markdown files to merge")
        
        # Create merged document
        merged_content = []
        
        # Add table of contents if requested
        if self.config.include_toc:
            toc = self.create_table_of_contents(all_files)
            merged_content.append(toc)
        
        current_category = None
        processed_files = 0
        total_size = 0
        
        for category, file_path in all_files:
            try:
                # Add category header when switching categories
                if category != current_category:
                    if current_category is not None:
                        merged_content.append("\n---\n")
                    
                    merged_content.append(f"\n# {category} Documentation\n")
                    current_category = category
                    print(f"📂 Processing {category} category...")
                
                # Read and process file
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if content.strip():
                    # Clean content
                    cleaned_content = self.clean_markdown_content(content, file_path)
                    
                    # Add section divider and content
                    merged_content.append(f"\n## {file_path.stem}\n")
                    merged_content.append(cleaned_content)
                    merged_content.append("\n")
                    
                    # Track statistics
                    total_size += len(content)
                    processed_files += 1
                    
                    # Progress indicator
                    if processed_files % 100 == 0:
                        print(f"  ✅ Processed {processed_files} files...")
                
            except Exception as e:
                print(f"  ⚠️ Error processing {file_path}: {e}")
                continue
        
        # Write merged file
        try:
            final_content = "\n".join(merged_content)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
            
            # Statistics
            final_size_mb = len(final_content) / (1024 * 1024)
            source_size_mb = total_size / (1024 * 1024)
            
            print(f"\n🎉 Successfully merged documentation!")
            print(f"📊 Final Statistics:")
            print(f"   • Files processed: {processed_files}")
            print(f"   • Source content: {source_size_mb:.1f} MB")
            print(f"   • Final merged file: {final_size_mb:.1f} MB")
            print(f"   • Output file: {output_path}")
            
            return str(output_path)
            
        except Exception as e:
            print(f"❌ Error writing merged file: {e}")
            return ""
    
    def run_full_pipeline(self, urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run complete extraction and merge pipeline"""
        print("🚀 Starting full documentation processing pipeline")
        print("=" * 60)
        
        # Step 1: Extract documents
        print("📥 STEP 1: Extracting documents...")
        extraction_result = self.extract_documents(urls)
        
        print("\n" + "=" * 60)
        
        # Step 2: Merge documents
        print("🔀 STEP 2: Merging documents...")
        merged_file = self.merge_documents()
        
        print("\n" + "=" * 60)
        print("🎉 PIPELINE COMPLETE!")
        print(f"📁 Extracted files: {self.output_dir}")
        print(f"📄 Merged document: {merged_file}")
        
        return {
            'extraction': extraction_result,
            'merged_file': merged_file,
            'success': bool(merged_file)
        }

def create_sample_config(output_path: str = "doc_processor_config.json"):
    """Create a sample configuration file"""
    config = ProcessingConfig(
        base_url="http://localhost:8080",
        url_list_file="urls.txt",
        output_dir="output/extracted_docs",
        merge_output="merged_documentation.md",
        max_workers=6,
        categories=['Other', 'Runtime', 'Editor', 'Plugins'],
        category_order=['Other', 'Runtime', 'Editor', 'Plugins']
    )
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(asdict(config), f, indent=2)
    
    print(f"📝 Sample configuration created: {output_path}")

def create_use_case(name: str, base_url: str = "http://localhost:8080", categories: List[str] = None):
    """Create a complete use case structure with configuration and directories"""
    if categories is None:
        categories = ['Documentation', 'API', 'Guides', 'Other']
    
    # Create use case directory
    use_case_dir = Path(f"use-cases/{name}")
    use_case_dir.mkdir(parents=True, exist_ok=True)
    
    # Create output directory
    output_dir = Path(f"output/{name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create configuration
    config = ProcessingConfig(
        base_url=base_url,
        url_list_file=None,
        start_urls=[base_url],
        output_dir=f"output/{name}",
        merge_output=f"output/{name}/merged_documentation.md",
        max_workers=6,
        categories=categories,
        category_order=categories
    )
    
    config_path = use_case_dir / "config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(asdict(config), f, indent=4)
    
    # Create README file
    readme_content = f"""# {name.title().replace('-', ' ')} Documentation Crawler

This use case is configured to crawl and process documentation from `{base_url}`.

## Purpose

Extracts, processes, and merges web documentation from {base_url} into clean markdown collections.

## Configuration

- **Base URL**: `{base_url}`
- **Output Directory**: `output/{name}/`
- **Merged Output**: `output/{name}/merged_documentation.md`
- **Categories**: {', '.join(categories)}

## Usage

### Quick Start
```bash
# Run complete processing pipeline
python use-cases/document-processing/doc_processor.py full-pipeline --config use-cases/{name}/config.json
```

### Step-by-Step Processing
```bash
# Extract documents only
python use-cases/document-processing/doc_processor.py extract --config use-cases/{name}/config.json

# Merge extracted documents
python use-cases/document-processing/doc_processor.py merge --config use-cases/{name}/config.json
```

### Verify Configuration
```bash
# Show help and available commands
python use-cases/document-processing/doc_processor.py --help

# Test configuration
python use-cases/document-processing/doc_processor.py create-config
```

## Output Structure

```
output/{name}/                      # Root output directory
├── {categories[0]}/                # {categories[0]} category
├── {categories[1]}/                # {categories[1]} documentation  
├── {categories[2]}/                # {categories[2]} documents
├── {categories[3] if len(categories) > 3 else 'Other'}/                          # {categories[3] if len(categories) > 3 else 'Other'} content
└── merged_documentation.md         # Combined documentation

use-cases/{name}/                   # Use case configuration
├── config.json                     # Configuration file
└── README.md                       # This file
```

## Configuration Details

- **Max Workers**: 6 (configurable for performance)
- **Timeout**: 15 seconds per request
- **Delay**: 0.1 seconds between requests (respectful crawling)
- **Content Processing**: Uses readability algorithm for clean extraction
- **Output Format**: Markdown with metadata headers
- **Table of Contents**: Automatically generated

## Prerequisites

Make sure your server at {base_url} is running before starting the crawl process.

## Performance

Expected processing rate: ~4-6 URLs per second with 6 worker threads on localhost servers.
"""
    
    readme_path = use_case_dir / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"✅ Use case '{name}' created successfully!")
    print(f"📁 Configuration: use-cases/{name}/config.json")
    print(f"📄 Documentation: use-cases/{name}/README.md") 
    print(f"📂 Output directory: output/{name}/")
    print(f"\n🚀 To start crawling:")
    print(f"python use-cases/document-processing/doc_processor.py full-pipeline --config use-cases/{name}/config.json")

def main():
    parser = argparse.ArgumentParser(description="Universal Document Processing Tool")
    parser.add_argument('command', choices=['extract', 'merge', 'full-pipeline', 'create-config', 'create-use-case'],
                       help='Command to execute')
    
    # Configuration
    parser.add_argument('--config', '-c', help='Configuration file (JSON or YAML)')
    parser.add_argument('--base-url', default='http://localhost:8080', help='Base URL for extraction')
    parser.add_argument('--urls-file', help='File containing URLs to process')
    parser.add_argument('--output-dir', default='output/extracted_docs', help='Output directory')
    parser.add_argument('--merge-output', default='merged_documentation.md', help='Merged output file')
    parser.add_argument('--max-workers', type=int, default=6, help='Number of worker threads')
    
    # Use case creation options
    parser.add_argument('--name', help='Name for new use case (required for create-use-case)')
    parser.add_argument('--categories', nargs='+', help='Categories for use case (space-separated)')
    
    # Processing options
    parser.add_argument('--input-dir', help='Input directory for merge operation')
    parser.add_argument('--title', default='Documentation', help='Title for merged document')
    parser.add_argument('--no-toc', action='store_true', help='Skip table of contents')
    parser.add_argument('--no-clean', action='store_true', help='Skip content cleaning')
    
    args = parser.parse_args()
    
    if args.command == 'create-config':
        create_sample_config()
        return
    
    if args.command == 'create-use-case':
        if not args.name:
            print("❌ Error: --name is required for create-use-case command")
            print("Example: python doc_processor.py create-use-case --name localhost-1313 --base-url http://localhost:1313")
            return
        create_use_case(
            name=args.name,
            base_url=args.base_url,
            categories=args.categories
        )
        return
    
    # Load or create configuration
    if args.config:
        processor = DocumentProcessor.from_config_file(args.config)
    else:
        config = ProcessingConfig(
            base_url=args.base_url,
            url_list_file=args.urls_file,
            output_dir=args.output_dir,
            merge_output=args.merge_output,
            max_workers=args.max_workers,
            include_toc=not args.no_toc,
            clean_content=not args.no_clean
        )
        processor = DocumentProcessor(config)
    
    # Execute command
    if args.command == 'extract':
        processor.extract_documents()
    elif args.command == 'merge':
        input_dir = Path(args.input_dir) if args.input_dir else None
        processor.merge_documents(input_dir, args.merge_output)
    elif args.command == 'full-pipeline':
        processor.run_full_pipeline()

if __name__ == "__main__":
    main()
