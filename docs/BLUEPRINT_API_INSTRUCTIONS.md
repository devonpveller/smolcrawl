# Processing UE5.4 Blueprint API Documentation

## Step-by-Step Instructions

### 1. Start Local HTTP Server
First, you need to serve the local HTML files via HTTP server. Open a new terminal/command prompt and run:

```bash
# Navigate to the Blueprint API documentation directory
cd "C:\Program Files\Epic Games\UE_5.4\Engine\Documentation\Builds\BlueprintAPI-HTML"

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
