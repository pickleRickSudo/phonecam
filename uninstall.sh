#!/bin/bash
# Stops Phone Cam and removes the login service.
LABEL=com.phonecam.server
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Phone Cam login service removed."
