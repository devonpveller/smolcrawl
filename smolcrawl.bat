@echo off
REM SmolCrawl - Main batch file launcher
REM Usage: smolcrawl.bat [command] [arguments]

setlocal enabledelayedexpansion

if "%1"=="" goto :show_help

set COMMAND=%1

if "%COMMAND%"=="help" goto :show_help
if "%COMMAND%"=="discover" goto :discover
if "%COMMAND%"=="create" goto :create
if "%COMMAND%"=="process" goto :process  
if "%COMMAND%"=="crawl" goto :crawl
if "%COMMAND%"=="test" goto :test

echo ❌ Unknown command: %COMMAND%
echo.
goto :show_help

:discover
shift
call discover-urls.bat %1 %2
goto :end

:create
shift
call create-use-case.bat %1 %2
goto :end

:process
shift
call process-docs.bat %1 %2
goto :end

:crawl
shift
call crawl-site.bat %1 %2
goto :end

:test
shift
call quick-test.bat %1
goto :end

:show_help
echo ================================
echo SmolCrawl - Documentation Crawler
echo ================================
echo.
echo Available commands:
echo.
echo   discover ^<base_url^> [output_file]
echo     Discover all URLs from a website
echo     Example: smolcrawl discover http://localhost:1313
echo.
echo   create ^<name^> ^<base_url^>
echo     Create a new use case configuration
echo     Example: smolcrawl create my-docs http://localhost:8080
echo.
echo   process ^<config_file^> [step]
echo     Process documentation from config file
echo     Steps: extract, merge, full-pipeline (default)
echo     Example: smolcrawl process use-cases\my-docs\config.json
echo.
echo   crawl ^<name^> ^<base_url^>
echo     Complete workflow: create use case, discover URLs, and process
echo     Example: smolcrawl crawl docker-docs http://localhost:1313
echo.
echo   test ^<base_url^>
echo     Quick test with first 5 URLs from a site
echo     Example: smolcrawl test http://localhost:1313
echo.
echo   help
echo     Show this help message
echo.
echo ================================
echo Quick Start:
echo 1. smolcrawl test http://localhost:1313
echo 2. smolcrawl crawl my-docs http://localhost:1313
echo ================================

:end
