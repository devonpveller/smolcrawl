@echo off
echo Starting batch test...
echo.

echo STEP 1: Create use case
echo ========================
python use-cases\document-processing\doc_processor.py create-use-case --name debug-test --base-url http://localhost:1313
echo Step 1 completed with exit code: %errorlevel%
echo About to start step 2...
timeout /t 2 /nobreak >nul
echo.

echo STEP 2: Discover URLs  
echo ========================
python use-cases\document-processing\doc_processor.py discover-urls --base-url http://localhost:1313 --save-urls debug_urls.txt
echo Step 2 completed with exit code: %errorlevel%
echo.

echo STEP 3: Full pipeline
echo ========================
python use-cases\document-processing\doc_processor.py full-pipeline --config use-cases\debug-test\config.json
echo Step 3 completed with exit code: %errorlevel%
echo.

echo ALL STEPS COMPLETED!
echo Press any key to exit...
pause
