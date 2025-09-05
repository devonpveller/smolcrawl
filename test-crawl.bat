@echo off
REM Simple test of the crawl process

echo Testing SmolCrawl with test-project and http://localhost:1313
echo.

set PROJECT_NAME=test-project
set WEBSITE_URL=http://localhost:1313

echo Step 1: Creating use case...
python use-cases\document-processing\doc_processor.py create-use-case --name %PROJECT_NAME% --base-url %WEBSITE_URL%
echo Exit code: %errorlevel%
echo.

echo Step 2: Discovering URLs...
python use-cases\document-processing\doc_processor.py discover-urls --base-url %WEBSITE_URL% --save-urls discovered_urls.txt
echo Exit code: %errorlevel%
echo.

echo Step 3: Running full pipeline...
python use-cases\document-processing\doc_processor.py full-pipeline --config use-cases\%PROJECT_NAME%\config.json
echo Exit code: %errorlevel%
echo.

echo Done!
pause
