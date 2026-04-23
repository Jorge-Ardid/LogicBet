@echo off
echo --- LOGICBET PREMIUM SYNC ---
cd /d "%~dp0python"
echo Check: Database maintenance...
if exist __pycache__ rmdir /s /q __pycache__
echo.
echo Running Python Sync Engine...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo !!! SYNC FAILED WITH ERROR %ERRORLEVEL% !!!
    echo Please check your internet connection or API limits.
    pause
) else (
    echo.
    echo --- SYNC SUCCESSFUL ---
    echo You can return to Godot now.
    timeout /t 5
)
