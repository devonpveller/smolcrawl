@echo off
echo ========================================
echo UE5.4 Blueprint API Documentation Processor
echo ========================================
echo.

echo Step 1: Testing if HTTP server is running...
python discover_blueprint_urls.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: HTTP server test failed
    echo Please start the HTTP server first:
    echo.
    echo 1. Open a new Command Prompt window
    echo 2. Run: cd "C:\Program Files\Epic Games\UE_5.4\Engine\Documentation\Builds\BlueprintAPI-HTML"
    echo 3. Run: python -m http.server 8081
    echo 4. Keep that window open and run this script again
    echo.
    pause
    exit /b 1
)

echo.
echo Step 2: Starting document processing...
python doc_processor.py full-pipeline --config config_blueprint_api.json
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Document processing failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS: Blueprint API documentation processed!
echo ========================================
echo Check these locations for results:
echo - Individual files: output\blueprint_api_docs\
echo - Merged document: UE54_Blueprint_API_Complete_Documentation.md
echo.
pause
