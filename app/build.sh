#!/bin/sh
# Builds "PAD Bot.app" into build/ and installs a copy in /Applications (~/Applications if that isn't writable). Needs only the
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
# Fixed requirement (bundle id only), so macOS keeps Screen Recording/Accessibility grants across rebuilds.
# shortcut: any app signed as local.padbot would match; use a real signing identity if this is ever shared.
codesign --force -s - -r='designated => identifier "local.padbot"' "$APP"
if [ "$1" != "--no-install" ]; then
  DEST=/Applications
  [ -w "$DEST" ] || { DEST="$HOME/Applications"; mkdir -p "$DEST"; }
  rm -rf "$DEST/PAD Bot.app" "$HOME/Applications/PAD Bot.app"  # one copy only, so Spotlight finds the current one
  cp -R "$APP" "$DEST/"
  echo "Installed $DEST/PAD Bot.app"
  OUT=$(mktemp)
  open -n -W "$DEST/PAD Bot.app" --args --permcheck "$OUT" && echo "Permissions: $(cat "$OUT")"
  rm -f "$OUT"
fi
