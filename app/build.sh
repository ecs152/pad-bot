#!/bin/sh
# Builds "PAD Bot.app" into build/ and installs a copy in ~/Applications. Needs only the
# Command Line Tools (swiftc). Re-run after changing app/Sources.
set -e
cd "$(dirname "$0")/.."
APP="build/PAD Bot.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
# SDK 26.5: the 27 SDK makes @State a macro whose plugin ships only with Xcode
swiftc -O -swift-version 5 -parse-as-library -sdk /Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk app/Sources/*.swift -o "$APP/Contents/MacOS/PADBot"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>PAD Bot</string>
  <key>CFBundleIdentifier</key><string>local.padbot</string>
  <key>CFBundleExecutable</key><string>PADBot</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>PadBotRoot</key><string>$(pwd)</string>
</dict></plist>
PLIST
codesign --force -s - "$APP"
if [ "$1" != "--no-install" ]; then
  mkdir -p "$HOME/Applications"
  rm -rf "$HOME/Applications/PAD Bot.app"
  cp -R "$APP" "$HOME/Applications/"
  echo "Installed ~/Applications/PAD Bot.app"
fi
