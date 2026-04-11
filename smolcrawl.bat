@echo off
REM SmolCrawl - Interactive Documentation Crawler
REM Simple batch file to crawl and process documentation sites

REM Set UTF-8 encoding to handle Unicode characters
chcp 65001 >nul

echo ================================
echo SmolCrawl - Documentation Crawler  
echo ================================
echo.

REM Get project name from user
set /p PROJECT_NAME="Enter project name (e.g., my-docs): "
if "%PROJECT_NAME%"=="" (
    echo X Project name cannot be empty
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

REM Get website URL from user
set /p WEBSITE_URL="Enter website URL (e.g., http://localhost:1313): "
if "%WEBSITE_URL%"=="" (
    echo X Website URL cannot be empty
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

REM Get server intensity from user
echo.
echo Server Intensity (how hard to hit the server):
echo   0.0 = Gentle  (1 worker, 2s delay, long timeout - slow but respectful)
echo   0.5 = Balanced (6 workers, 1s delay, medium timeout - recommended)
echo   1.0 = Aggressive (12 workers, no delay, short timeout - fast but intensive)
echo.
set /p SERVER_INTENSITY="Enter server intensity (0.0-1.0, default 0.3): "
if "%SERVER_INTENSITY%"=="" set SERVER_INTENSITY=0.3

echo.
echo ================================
echo Starting SmolCrawl Process
echo ================================
echo Project Name: %PROJECT_NAME%
echo Website URL: %WEBSITE_URL%
echo Server Intensity: %SERVER_INTENSITY%
echo.
echo This will create:
echo   - use-cases\%PROJECT_NAME%\ (configuration and URLs)
echo   - output\%PROJECT_NAME%\ (extracted documents)
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause >nul

echo.
echo Starting autonomous crawl process...
echo Please wait, this process will run automatically...
echo.

REM Step 1: Create use case
echo [1/3] Creating use case configuration...
call python use-cases\document-processing\doc_processor.py create-use-case --name "%PROJECT_NAME%" --base-url "%WEBSITE_URL%"
if not %errorlevel%==0 (
    echo X Failed to create use case
    echo Press any key to exit...
    pause >nul
    exit /b 1
)
echo [1/3] Use case created successfully!

echo.
echo [2/3] Discovering URLs from website...
call python use-cases\document-processing\doc_processor.py discover-urls --base-url "%WEBSITE_URL%" --save-urls "use-cases\%PROJECT_NAME%\discovered_urls.txt"
if not %errorlevel%==0 (
    echo X Failed to discover URLs
    echo Press any key to exit...
    pause >nul
    exit /b 1
)
echo [2/3] URLs discovered successfully!

echo.
echo [3/3] Processing documents (this may take several minutes)...
echo     Using server intensity %SERVER_INTENSITY% (auto-configured settings)...
call python use-cases\document-processing\doc_processor.py extract --base-url "%WEBSITE_URL%" --urls-file "use-cases\%PROJECT_NAME%\discovered_urls.txt" --output-dir "output\%PROJECT_NAME%" --server-intensity %SERVER_INTENSITY%
if not %errorlevel%==0 (
    echo X Failed to extract documents
    echo Press any key to exit...
    pause >nul
    exit /b 1
)
echo [3a/3] Document extraction completed successfully!

echo.
echo [3b/3] Merging documents...
call python use-cases\document-processing\doc_processor.py merge --input-dir "output\%PROJECT_NAME%" --merge-output "output\%PROJECT_NAME%\%PROJECT_NAME%_merged.md"
if not %errorlevel%==0 (
    echo X Failed to merge documents
    echo Press any key to exit...
    pause >nul
    exit /b 1
)
echo [3/3] Processing completed successfully!

echo.
echo ================================
echo Optional: Upload to Open WebUI
echo ================================
echo.
set /p OWUI_UPLOAD="Would you like to upload to Open WebUI? (y/n, default n): "
if /i "%OWUI_UPLOAD%"=="y" (
    set /p OWUI_URL="  Open WebUI URL [http://localhost:3000]: "
    if "%OWUI_URL%"=="" set OWUI_URL=http://localhost:3000
    set /p OWUI_API_KEY="  API Key: "
    if "%OWUI_API_KEY%"=="" (
        echo X API Key is required for OWUI upload
        goto :skip_owui
    )
    set /p KB_NAME="  Knowledge Base Name [SmolCrawl - %PROJECT_NAME%]: "
    if "%KB_NAME%"=="" set KB_NAME=SmolCrawl - %PROJECT_NAME%

    echo.
    echo [4/4] Uploading to Open WebUI knowledge base...
    call python use-cases\document-processing\doc_processor.py owui-sync --input-dir "output\%PROJECT_NAME%" --owui-url "%OWUI_URL%" --owui-api-key "%OWUI_API_KEY%" --kb-name "%KB_NAME%"
    if not %errorlevel%==0 (
        echo X Failed to upload to Open WebUI
        echo Continuing without OWUI upload...
    ) else (
        echo [4/4] Upload to Open WebUI completed!
    )
)
:skip_owui

echo.
echo ================================
echo ^ SmolCrawl completed successfully!
echo ================================
echo.
echo Results available in:
echo   - use-cases\%PROJECT_NAME%\
echo   - output\%PROJECT_NAME%\
echo.
echo Press any key to exit...
pause >nul
