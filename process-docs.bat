@echo off
REM SmolCrawl - Process documentation from config
REM Usage: process-docs.bat <config_file> [step]

setlocal enabledelayedexpansion

if "%1"=="" (
    echo Usage: process-docs.bat ^<config_file^> [step]
    echo Steps: extract, merge, full-pipeline (default)
    echo Example: process-docs.bat use-cases\localhost-1313\config.json
    echo Example: process-docs.bat use-cases\localhost-1313\config.json extract
    exit /b 1
)

set CONFIG_FILE=%1
set STEP=%2

if "%STEP%"=="" (
    set STEP=full-pipeline
)

if not exist "%CONFIG_FILE%" (
    echo ❌ Config file not found: %CONFIG_FILE%
    exit /b 1
)

echo ================================
echo SmolCrawl - Process Documentation
echo ================================
echo Config: %CONFIG_FILE%
echo Step: %STEP%
echo ================================

python use-cases\document-processing\doc_processor.py %STEP% --config "%CONFIG_FILE%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Documentation processing completed!
    
    if "%STEP%"=="full-pipeline" (
        echo 📁 Check the output directory specified in your config
        echo 📄 Merged documentation should be available
    )
    if "%STEP%"=="extract" (
        echo 📁 Individual files extracted to output directory
        echo 💡 Run: process-docs.bat "%CONFIG_FILE%" merge
    )
    if "%STEP%"=="merge" (
        echo 📄 Merged documentation created
    )
) else (
    echo.
    echo ❌ Documentation processing failed!
    exit /b %ERRORLEVEL%
)
