@echo off
echo Testing with call command...
echo.

echo STEP 1:
call :run_step1
echo After step 1

echo STEP 2:  
call :run_step2
echo After step 2

echo STEP 3:
call :run_step3
echo After step 3

echo ALL DONE!
pause
goto :eof

:run_step1
echo Running create-use-case...
python use-cases\document-processing\doc_processor.py create-use-case --name call-test --base-url http://localhost:1313
echo create-use-case completed
goto :eof

:run_step2
echo Running discover-urls...
python use-cases\document-processing\doc_processor.py discover-urls --base-url http://localhost:1313 --save-urls call_urls.txt
echo discover-urls completed  
goto :eof

:run_step3
echo Running full-pipeline...
python use-cases\document-processing\doc_processor.py full-pipeline --config use-cases\call-test\config.json
echo full-pipeline completed
goto :eof
