@echo off
echo ========================================
echo LogicBet Mobile Build Script
echo ========================================
echo.

REM Check if Godot is installed
where godot >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Godot not found in PATH
    echo Please install Godot 4.5 or later from https://godotengine.org/download
    echo Or add Godot to your system PATH
    pause
    exit /b 1
)

echo Select platform to build:
echo 1. Android (APK)
echo 2. iOS (IPA)
echo 3. Both
echo.
set /p choice="Enter choice (1-3): "

if "%choice%"=="1" goto android
if "%choice%"=="2" goto ios
if "%choice%"=="3" goto both
echo Invalid choice
pause
exit /b 1

:android
echo.
echo ========================================
echo Building Android APK...
echo ========================================
cd godot_app
godot --headless --export-release "Android" "../LogicBet.apk"
if %errorlevel% equ 0 (
    echo.
    echo SUCCESS: Android APK built at ../LogicBet.apk
    echo You can install this on your Android device
) else (
    echo.
    echo ERROR: Android build failed
)
cd ..
pause
exit /b 0

:ios
echo.
echo ========================================
echo Building iOS IPA...
echo ========================================
echo NOTE: iOS build requires macOS and Xcode
echo This script will export the project, but you need:
echo 1. macOS computer
echo 2. Xcode installed
echo 3. Apple Developer account for signing
echo.
pause
cd godot_app
godot --headless --export-release "iOS" "../LogicBet.ipa"
if %errorlevel% equ 0 (
    echo.
    echo SUCCESS: iOS project exported at ../LogicBet.ipa
    echo Complete the build in Xcode on macOS
) else (
    echo.
    echo ERROR: iOS export failed
)
cd ..
pause
exit /b 0

:both
echo.
echo ========================================
echo Building both platforms...
echo ========================================
cd godot_app
godot --headless --export-release "Android" "../LogicBet.apk"
if %errorlevel% equ 0 (
    echo SUCCESS: Android APK built
) else (
    echo ERROR: Android build failed
)
godot --headless --export-release "iOS" "../LogicBet.ipa"
if %errorlevel% equ 0 (
    echo SUCCESS: iOS project exported
) else (
    echo ERROR: iOS export failed
)
cd ..
pause
exit /b 0
