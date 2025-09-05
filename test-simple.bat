@echo off
echo Step 1: Testing create-use-case...
python use-cases\document-processing\doc_processor.py create-use-case --name test-batch --base-url http://localhost:1313
echo Exit code from step 1: %errorlevel%
echo.

echo Step 2: Testing discover-urls...
python use-cases\document-processing\doc_processor.py discover-urls --base-url http://localhost:1313 --save-urls test_urls.txt
echo Exit code from step 2: %errorlevel%
echo.

echo Step 3: Testing full-pipeline...
python use-cases\document-processing\doc_processor.py full-pipeline --config use-cases\test-batch\config.json
echo Exit code from step 3: %errorlevel%
echo.

echo All steps completed!
pause
