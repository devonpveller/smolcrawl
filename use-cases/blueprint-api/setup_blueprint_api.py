#!/usr/bin/env python3
"""
Blueprint API Setup Helper
Helps set up processing for local Unreal Engine 5.4 Blueprint API documentation
"""

import json
from pathlib import Path

def create_blueprint_config():
    """Create a configuration file for Blueprint API processing"""
    
    config = {
        "base_url": "http://localhost:8081",
        "url_list_file": "blueprint_api_urls.txt",
        "max_workers": 8,
        "timeout": 30,
        "delay_between_requests": 0.05,
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
    
    print(f"✅ Created Blueprint API configuration: {config_file}")
    return config_file

def create_instructions():
    """Create step-by-step instructions"""
    
    instructions = """# Processing UE5.4 Blueprint API Documentation

## Step-by-Step Instructions

### 1. Start Local HTTP Server
First, you need to serve the local HTML files via HTTP server. Open a new terminal/command prompt and run:

```bash
# Navigate to the Blueprint API documentation directory
cd "C:\\Program Files\\Epic Games\\UE_5.4\\Engine\\Documentation\\Builds\\BlueprintAPI-HTML"

# Start Python HTTP server on port 8081
python -m http.server 8081
```

Keep this terminal open while processing.

### 2. Test Server Access
Open your browser and go to: http://localhost:8081
You should see the Blueprint API documentation files.

### 3. Create URL List (Manual Method)
If the automated discovery doesn't work, you can manually create a URL list:

```bash
# In the SmolCrawl directory, create blueprint_api_urls.txt with URLs like:
http://localhost:8081/index.html
http://localhost:8081/Classes/index.html
http://localhost:8081/Functions/index.html
# ... add more URLs as needed
```

### 4. Run Document Processing
In the SmolCrawl directory, run:

```bash
python doc_processor.py full-pipeline --config config_blueprint_api.json
```

### 5. Alternative: Use Automated Script
Run the automated processor:

```bash
python process_blueprint_api.py
```

## Expected Output

- **Individual Files**: `output/blueprint_api_docs/` with categorized markdown files
- **Merged Document**: `UE54_Blueprint_API_Complete_Documentation.md`

## Troubleshooting

### Server Issues
- Make sure port 8081 is not in use
- Try a different port and update the config file
- Check Windows Firewall settings

### File Access Issues  
- Run command prompt as Administrator if needed
- Verify the UE5.4 installation path
- Check file permissions

### Processing Issues
- Reduce `max_workers` if you encounter timeout errors
- Increase `timeout` value for slow responses
- Check the server is still running

## Configuration Options

Edit `config_blueprint_api.json` to customize:
- `max_workers`: Number of concurrent threads (default: 8)
- `timeout`: Request timeout in seconds (default: 30) 
- `delay_between_requests`: Pause between requests (default: 0.05)
- `categories`: Document categorization (customize for Blueprint API structure)
"""
    
    instructions_file = Path("BLUEPRINT_API_INSTRUCTIONS.md")
    with open(instructions_file, 'w', encoding='utf-8') as f:
        f.write(instructions)
    
    print(f"📋 Created instructions: {instructions_file}")
    return instructions_file

def main():
    print("🎯 Blueprint API Documentation Setup")
    print("="*50)
    
    # Create configuration
    config_file = create_blueprint_config()
    
    # Create instructions
    instructions_file = create_instructions()
    
    print(f"\n✅ Setup completed!")
    print(f"📖 Read instructions: {instructions_file}")
    print(f"⚙️ Configuration ready: {config_file}")
    
    print(f"\n🚀 Quick start:")
    print(f"1. Open new terminal and run:")
    print(f'   cd "C:\\Program Files\\Epic Games\\UE_5.4\\Engine\\Documentation\\Builds\\BlueprintAPI-HTML"')
    print(f"   python -m http.server 8081")
    print(f"2. In this directory, run:")
    print(f"   python process_blueprint_api.py")

if __name__ == "__main__":
    main()
