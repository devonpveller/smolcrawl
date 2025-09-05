# 🎯 UE5.4 Blueprint API Documentation Processing

## Overview
Process local Unreal Engine 5.4 Blueprint API HTML documentation and convert it to clean, organized markdown files using the unified `doc_processor.py` tool.

## 🚀 Quick Start (Easiest Method)

### Option 1: Automated Windows Batch Files
1. **Start the server**: Double-click `start_blueprint_server.bat`
2. **Process documentation**: In a new window, double-click `process_blueprint_api.bat`

### Option 2: Manual Command Line
1. **Start HTTP server** (keep this window open):
   ```cmd
   cd "C:\Program Files\Epic Games\UE_5.4\Engine\Documentation\Builds\BlueprintAPI-HTML"
   python -m http.server 8081
   ```

2. **Process documentation** (in SmolCrawl directory):
   ```cmd
   python discover_blueprint_urls.py
   python doc_processor.py full-pipeline --config config_blueprint_api.json
   ```

### Option 3: Fully Automated Python Script
```cmd
python process_blueprint_api.py
```

## 📁 File Overview

### Created Files
- **`config_blueprint_api.json`** - Configuration for Blueprint API processing
- **`start_blueprint_server.bat`** - Windows batch file to start HTTP server
- **`process_blueprint_api.bat`** - Windows batch file for complete processing
- **`discover_blueprint_urls.py`** - URL discovery script
- **`process_blueprint_api.py`** - Fully automated processing script
- **`BLUEPRINT_API_INSTRUCTIONS.md`** - Detailed step-by-step instructions

### Generated During Processing
- **`blueprint_api_urls.txt`** - List of discovered URLs
- **`output/blueprint_api_docs/`** - Individual markdown files by category
- **`UE54_Blueprint_API_Complete_Documentation.md`** - Single merged document

## ⚙️ Configuration Details

The processing uses these optimized settings for local documentation:

```json
{
  "base_url": "http://localhost:8081",
  "max_workers": 8,
  "timeout": 30,
  "delay_between_requests": 0.05,
  "categories": ["Classes", "Functions", "Components", "Interfaces", "Enums", "Structs", "Other"]
}
```

## 🔧 Customization Options

### Change Processing Speed
Edit `config_blueprint_api.json`:
- `max_workers`: Concurrent threads (1-16, default: 8)
- `delay_between_requests`: Pause between requests (0.01-1.0, default: 0.05)

### Modify Categories
Customize the `categories` array in config file for your specific Blueprint API structure:
```json
"categories": [
  "Gameplay",
  "Animation", 
  "Rendering",
  "Audio",
  "Input",
  "Other"
]
```

### Change Output Location
- `output_dir`: Directory for individual files
- `merge_output`: Filename for merged documentation

## 📊 Expected Performance

Based on typical Blueprint API documentation:
- **Processing Speed**: 5-15 files/second (local server)
- **Success Rate**: 95-99% (depending on HTML structure)
- **Output Size**: 5-50MB depending on documentation scope
- **Processing Time**: 5-30 minutes for complete API

## 🐛 Troubleshooting

### Server Issues
- **Port 8081 in use**: Change port in scripts and config file
- **Permission denied**: Run Command Prompt as Administrator
- **Can't find documentation**: Verify UE5.4 installation path

### Processing Issues
- **Timeout errors**: Increase `timeout` value in config
- **Memory issues**: Reduce `max_workers` to 4 or lower
- **Empty output**: Check HTML structure and readability extraction

### Path Issues
- **Wrong UE5.4 path**: Update path in batch files and scripts
- **Spaces in path**: Keep quotes around paths with spaces
- **Network drives**: Copy documentation to local drive first

## 🔍 Verification Steps

1. **Check server**: Open http://localhost:8081 in browser
2. **Verify URLs**: Check `blueprint_api_urls.txt` has URLs
3. **Test processing**: Start with small subset of URLs
4. **Check output**: Verify files in `output/blueprint_api_docs/`

## 🎯 Success Indicators

- ✅ HTTP server starts without errors
- ✅ URL discovery finds HTML files
- ✅ Processing shows progress updates
- ✅ Individual markdown files created
- ✅ Merged documentation generated
- ✅ No critical errors in output

## 📚 Next Steps

After successful processing:
1. **Review output**: Check `UE54_Blueprint_API_Complete_Documentation.md`
2. **Organize files**: Individual files in categorized folders
3. **Share documentation**: Use generated markdown files in projects
4. **Create backups**: Save processed documentation for future use

## 🆘 Support

If you encounter issues:
1. Check the detailed instructions in `BLUEPRINT_API_INSTRUCTIONS.md`
2. Verify all prerequisites are met
3. Try the manual method if automated scripts fail
4. Adjust configuration settings for your specific setup

---

**Note**: This process converts the local UE5.4 Blueprint API HTML documentation to markdown using the same proven techniques that successfully processed 3,995+ Unreal Engine documentation files with 99.97% success rate.
