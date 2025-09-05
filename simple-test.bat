@echo off
REM SmolCrawl - Simple quick test
REM Usage: simple-test.bat <base_url>

if "%1"=="" (
    echo Usage: simple-test.bat ^<base_url^>
    echo Example: simple-test.bat http://localhost:1313
    pause
    exit /b 1
)

set BASE_URL=%1

echo ================================
echo SmolCrawl - Simple Test
echo ================================
echo Base URL: %BASE_URL%
echo ================================

echo.
echo Step 1: Discovering URLs...
python use-cases\document-processing\doc_processor.py discover-urls --base-url "%BASE_URL%" --save-urls "%CD%\test_urls_temp.txt"

echo.
echo Step 2: Creating small test set...
python batch_helper.py create_test_urls "%CD%\test_urls_temp.txt" "%CD%\quick_test_urls.txt" 5

echo.
echo Step 3: Creating test config...
python batch_helper.py create_test_config "%BASE_URL%" "%CD%\quick_test_urls.txt" "%CD%\quick_test_config.json"

echo.
echo Step 4: Processing documentation...
python use-cases\document-processing\doc_processor.py full-pipeline --config "%CD%\quick_test_config.json"

echo.
echo Step 5: Cleaning up...
del test_urls_temp.txt 2>nul
del quick_test_urls.txt 2>nul
del quick_test_config.json 2>nul

echo.
echo ================================
echo SIMPLE TEST COMPLETE!
echo ================================
echo Check output\quick-test\ for results
echo ================================
pause
