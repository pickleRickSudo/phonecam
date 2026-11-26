#!/bin/bash
# Builds "Phone Cam Menu.app" (the menu bar "p" icon) into ~/Applications
# and starts it at login.
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Applications/Phone Cam Menu.app"
LABEL=com.phonecam.menubar
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$APP/Contents/MacOS" "$HOME/Library/LaunchAgents"
swiftc -O -o "$APP/Contents/MacOS/PhoneCamMenu" "$DIR/tools/menubar.swift"
cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Phone Cam Menu</string>
  <key>CFBundleIdentifier</key><string>$LABEL</string>
  <key>CFBundleExecutable</key><string>PhoneCamMenu</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
</dict></plist>
PL
codesign --force --sign - "$APP" >/dev/null 2>&1 || true

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$APP/Contents/MacOS/PhoneCamMenu</string></array>
  <key>RunAtLoad</key><true/>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Menu bar icon running: $APP"
