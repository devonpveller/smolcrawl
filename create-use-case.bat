@echo off
REM SmolCrawl - Create a new use case configuration
REM Usage: create-use-case.bat <name> <base_url>

setlocal enabledelayedexpansion

if "%2"=="" (
    echo Usage: create-use-case.bat ^<name^> ^<base_url^>
    echo Example: create-use-case.bat my-docs http://localhost:8080
    exit /b 1
)

set USE_CASE_NAME=%1
set BASE_URL=%2

echo ================================
echo SmolCrawl - Create Use Case
echo ================================
echo Name: %USE_CASE_NAME%
echo Base URL: %BASE_URL%
echo ================================

python use-cases\document-processing\doc_processor.py create-use-case --name "%USE_CASE_NAME%" --base-url "%BASE_URL%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Use case created successfully!
    echo 📁 Directory: use-cases\%USE_CASE_NAME%
    echo 📝 Config: use-cases\%USE_CASE_NAME%\config.json
    echo.
    echo Next steps:
    echo 1. discover-urls.bat "%BASE_URL%" use-cases\%USE_CASE_NAME%\discovered_urls.txt
    echo 2. Edit use-cases\%USE_CASE_NAME%\config.json to use discovered_urls.txt
    echo 3. process-docs.bat use-cases\%USE_CASE_NAME%\config.json
) else (
    echo.
    echo ❌ Use case creation failed!
    exit /b %ERRORLEVEL%
)
