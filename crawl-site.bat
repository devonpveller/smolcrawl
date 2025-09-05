@echo off
REM SmolCrawl - Complete workflow for new documentation site
REM Usage: crawl-site.bat <name> <base_url>

setlocal enabledelayedexpansion

if "%2"=="" (
    echo Usage: crawl-site.bat ^<name^> ^<base_url^>
    echo Example: crawl-site.bat docker-docs http://localhost:1313
    exit /b 1
)

set USE_CASE_NAME=%1
set BASE_URL=%2

echo ================================
echo SmolCrawl - Complete Site Crawl
echo ================================
echo Name: %USE_CASE_NAME%
echo Base URL: %BASE_URL%
echo ================================

echo.
echo 📋 Step 1: Creating use case...
call create-use-case.bat "%USE_CASE_NAME%" "%BASE_URL%"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

echo.
echo 🔍 Step 2: Discovering URLs...
call discover-urls.bat "%BASE_URL%" "use-cases\%USE_CASE_NAME%\discovered_urls.txt"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

echo.
echo 📝 Step 3: Updating config to use discovered URLs...
python batch_helper.py update_use_case_config "%USE_CASE_NAME%"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

echo.
echo 🚀 Step 4: Processing all documentation...
call process-docs.bat "use-cases\%USE_CASE_NAME%\config.json"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

echo.
echo ================================
echo 🎉 COMPLETE! 
echo ================================
echo 📁 Use case: use-cases\%USE_CASE_NAME%\
echo 📄 Merged docs: use-cases\%USE_CASE_NAME%\output\%USE_CASE_NAME%\merged_documentation.md
echo ================================
