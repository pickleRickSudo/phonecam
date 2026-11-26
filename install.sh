#!/bin/bash
# Installs Phone Cam as a login service (starts at login, restarts if it stops).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL=com.phonecam.server
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
for t in adb ffmpeg scrcpy; do
  command -v "$t" >/dev/null || PATH="/opt/homebrew/bin:$PATH"
  command -v "$t" >/dev/null || { echo "Missing $t. Install with: brew install scrcpy ffmpeg && brew install --cask android-platform-tools"; exit 1; }
done
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>$DIR/server.py</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$DIR/server.log</string>
  <key>StandardErrorPath</key><string>$DIR/server.log</string>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Phone Cam is running: http://127.0.0.1:8737/"
echo "In Safari: open that page, then File > Add to Dock."
