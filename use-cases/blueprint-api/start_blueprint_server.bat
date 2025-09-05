@echo off
echo ========================================
echo Starting HTTP Server for Blueprint API Docs
echo ========================================
echo.

set "DOCS_PATH=C:\Program Files\Epic Games\UE_5.4\Engine\Documentation\Builds\BlueprintAPI-HTML"

echo Checking if documentation directory exists...
if not exist "%DOCS_PATH%" (
    echo ERROR: Documentation directory not found:
    echo %DOCS_PATH%
    echo.
    echo Please verify:
    echo 1. Unreal Engine 5.4 is installed
    echo 2. Blueprint API documentation is installed
    echo 3. The path is correct
    echo.
    pause
    exit /b 1
)

echo Found documentation directory: %DOCS_PATH%
echo.
echo Starting HTTP server on port 8081...
echo IMPORTANT: Keep this window open while processing documentation!
echo.
echo You can test the server by opening: http://localhost:8081
echo.
echo To stop the server, press Ctrl+C
echo.

cd /d "%DOCS_PATH%"
python -m http.server 8081
