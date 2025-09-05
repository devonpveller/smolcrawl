@echo off
REM SmolCrawl - Discover URLs from a website
REM Usage: discover-urls.bat http://example.com [output_file]

setlocal enabledelayedexpansion

if "%1"=="" (
    echo Usage: discover-urls.bat ^<base_url^> [output_file]
    echo Example: discover-urls.bat http://localhost:1313
    echo Example: discover-urls.bat http://localhost:1313 my_urls.txt
    exit /b 1
)

set BASE_URL=%1
set OUTPUT_FILE=%2

if "%OUTPUT_FILE%"=="" (
    set OUTPUT_FILE=discovered_urls.txt
)

echo ================================
echo SmolCrawl URL Discovery
echo ================================
echo Base URL: %BASE_URL%
echo Output file: %OUTPUT_FILE%
echo ================================

python use-cases\document-processing\doc_processor.py discover-urls --base-url "%BASE_URL%" --save-urls "%OUTPUT_FILE%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ URL discovery completed!
    echo 📄 URLs saved to: %OUTPUT_FILE%
) else (
    echo.
    echo ❌ URL discovery failed!
    exit /b %ERRORLEVEL%
)
