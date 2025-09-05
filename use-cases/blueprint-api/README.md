# Blueprint API Documentation Processing

This directory contains all files related to processing Unreal Engine 5.4 Blueprint API documentation.

## Files

### Core Processing Scripts
- `blueprint_api_assistant.py` - Interactive assistant for Blueprint API processing
- `process_blueprint_api.py` - Main processing script for Blueprint API
- `setup_blueprint_api.py` - Setup script for Blueprint API processing environment

### URL Discovery
- `discover_blueprint_urls.py` - Discovers Blueprint API URLs from documentation
- `discover_blueprint_urls_win.py` - Windows-compatible version with Unicode handling

### Monitoring
- `monitor_blueprint_progress.py` - Monitors processing progress in real-time

### Configuration
- `config_blueprint_api.json` - Configuration file optimized for Blueprint API processing
- `blueprint_api_urls.txt` - Generated list of Blueprint API URLs

### Batch Scripts (Windows)
- `process_blueprint_api.bat` - Windows batch file for easy processing
- `start_blueprint_server.bat` - Starts local HTTP server for documentation
- `node.bat` - Node.js runner
- `npm.bat` - NPM runner

## Usage

1. Run `setup_blueprint_api.py` to configure the environment
2. Use `discover_blueprint_urls_win.py` to find all Blueprint API URLs
3. Execute `process_blueprint_api.py` or use the interactive `blueprint_api_assistant.py`
4. Monitor progress with `monitor_blueprint_progress.py`

## Output

Processed documentation will be saved in the main `output/` directory with proper categorization into Classes, Components, and Other types.
