#!/bin/bash
# Starts the Phone Cam server (if it isn't running) and opens its control page.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
DIR="$(cd "$(dirname "$0")" && pwd)"
URL="http://127.0.0.1:8737/"
if ! curl -fsS -m 1 "${URL}api/status" >/dev/null 2>&1; then
  nohup /usr/bin/python3 "$DIR/server.py" >"$DIR/server.log" 2>&1 &
  for _ in $(seq 1 30); do
    curl -fsS -m 1 "${URL}api/status" >/dev/null 2>&1 && break
    sleep 0.2
  done
fi
open "$URL"
