# LogicBet Mobile Build Instructions

## Overview
This guide explains how to build the LogicBet app for mobile devices (Android and iOS).

## Prerequisites

### For Android:
- Godot 4.5 or later installed
- Android SDK installed (comes with Godot)
- Java Development Kit (JDK) 11 or later
- Android device for testing (optional)

### For iOS:
- macOS computer
- Godot 4.5 or later installed
- Xcode 15 or later
- Apple Developer account (for App Store distribution)
- iOS device for testing (optional)

## Quick Build

### Windows:
```bash
BUILD_MOBILE.bat
```

### Manual Build Commands

#### Android:
```bash
cd godot_app
godot --headless --export-release "Android" "../LogicBet.apk"
```

#### iOS (macOS only):
```bash
cd godot_app
godot --headless --export-release "iOS" "../LogicBet.ipa"
```

## Platform-Specific Instructions

### Android

1. **Install Godot**: Download from https://godotengine.org/download
2. **Add Godot to PATH**: Add Godot executable to your system PATH
3. **Run the build script**: Execute `BUILD_MOBILE.bat` and select option 1
4. **Install APK**: Transfer `LogicBet.apk` to your Android device and install

**Note**: The APK will be unsigned. For Play Store distribution, you need to:
- Create a keystore
- Sign the APK
- Upload to Google Play Console

### iOS

1. **Install Godot on macOS**: Download from https://godotengine.org/download
2. **Install Xcode**: Download from Mac App Store
3. **Export project**: Run the build script or manual command
4. **Open in Xcode**: The export creates an Xcode project
5. **Configure signing**: Add your Apple Developer credentials
6. **Build**: Build and run from Xcode

**Note**: iOS requires code signing. You need an Apple Developer account ($99/year) for App Store distribution.

## Export Presets Configuration

The project includes pre-configured export presets:

- **Android**: `godot_app/export_presets.cfg` (preset.0)
  - Package: org.logicbet.app
  - App Name: LogicBet
  - Architecture: ARM64
  - Internet permission: enabled

- **iOS**: `godot_app/export_presets.cfg` (preset.2)
  - Bundle ID: org.logicbet.app
  - Min iOS: 13.0
  - Target iOS: 17.0

## Troubleshooting

### Android Build Fails:
- Ensure Godot is in your PATH
- Check that Android SDK is properly installed in Godot Editor > Editor > Export > Android
- Verify Java JDK is installed

### iOS Export Fails:
- Must be done on macOS
- Xcode must be installed
- Command line tools must be installed: `xcode-select --install`

## Testing

### Android:
1. Enable "Unknown Sources" in device settings
2. Transfer APK to device via USB or cloud
3. Tap APK to install
4. Grant internet permission when prompted

### iOS:
1. Connect iOS device to Mac
2. Build and run from Xcode
3. Trust developer certificate in Settings > General > VPN & Device Management

## Database

The app includes the SQLite database (`logicbet.db`) embedded in the export. For production, consider:
- Using a remote database server
- Implementing data sync
- Adding user authentication

## API Configuration

The app uses APIs configured in `data/api_config.json`. Ensure API keys are valid before building.

## Support

For issues with:
- Godot: https://github.com/godotengine/godot/issues
- Android export: https://docs.godotengine.org/en/stable/tutorials/export/android_export.html
- iOS export: https://docs.godotengine.org/en/stable/tutorials/export/ios_export.html
