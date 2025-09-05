@echo off
REM SmolCrawl - Quick test with small URL set
REM Usage: quick-test.bat <base_url>

setlocal enabledelayedexpansion

if "%1"=="" (
    echo Usage: quick-test.bat ^<base_url^>
    echo Example: quick-test.bat http://localhost:1313
    exit /b 1
)

set BASE_URL=%1

echo ================================
echo SmolCrawl - Quick Test
echo ================================
echo Base URL: %BASE_URL%
echo ================================

echo.
echo 🔍 Step 1: Discovering URLs...
call discover-urls.bat "%BASE_URL%" "%CD%\test_urls_temp.txt"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

echo.
echo 📝 Step 2: Creating small test set (first 5 URLs)...
python batch_helper.py create_test_urls "test_urls_temp.txt" "quick_test_urls.txt" 5
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

echo.
echo 📝 Step 3: Creating test config...
python batch_helper.py create_test_config "%BASE_URL%" "quick_test_urls.txt" "quick_test_config.json"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

echo.
echo 🚀 Step 4: Processing test documentation...
call process-docs.bat "quick_test_config.json"

echo.
echo 🧹 Step 5: Cleaning up temporary files...
del test_urls_temp.txt 2>nul
del quick_test_urls.txt 2>nul
del quick_test_config.json 2>nul

echo.
echo ================================
echo 🎉 QUICK TEST COMPLETE!
echo ================================
echo 📁 Results: output\quick-test\
echo 📄 Merged: output\quick-test\merged_documentation.md
echo ================================
