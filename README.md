# Phone Cam

Use an Android phone's camera on a Mac over **USB only** (no Wi-Fi), as an **OBS Browser source**. There is no mirroring window to keep open.

<img src="icon.png" width="96" alt="Phone Cam icon">

A small local web app lets you pick the camera, quality (720p / 1080p / 4K), frame rate and rotation, then press **Start**. OBS loads a fixed link, `http://127.0.0.1:8737/view`. The link never changes, and OBS picks the picture back up by itself after a stop or restart.

## Features

- Back, back-alt, front and front-alt cameras; 720p, 1080p and 4K; 24 or 30 fps; rotate by 0, 90, 180 or 270°
- Live preview with an optional 3×3 grid. The grid is shown only in the control app, never in OBS.
- **Measure delay**: flashes the screen white and times how long the camera takes to see it, then tells you the OBS Render Delay and audio Sync Offset to use
- Runs as a login service, and can be added to the Dock as a Safari web app

## How it works

```
phone camera ─► scrcpy-server (raw H.264, over adb USB) ─► ffmpeg (H.264 → MJPEG)
            ─► Python stdlib HTTP server ─► /view (OBS Browser source) + control UI
```

It starts [scrcpy](https://github.com/Genymobile/scrcpy)'s phone-side server directly with `raw_stream=true video_source=camera`. That avoids the scrcpy window and the buffering of recording to a container, which added about 18 s of delay. Decoding with a single thread and `low_delay` brings the total delay to about 250 ms on a Galaxy S10+.

## Requirements

- macOS with Homebrew: `brew install scrcpy ffmpeg` and `brew install --cask android-platform-tools`
- An Android 12+ phone (the scrcpy camera source needs Android 12) with **USB debugging** on and this Mac allowed
- The `/usr/bin/python3` that ships with macOS. Nothing else is needed.

## Install

```bash
git clone https://github.com/pickleRickSudo/phonecam.git ~/tools/phonecam
cd ~/tools/phonecam
./install.sh        # login service on http://127.0.0.1:8737/
```

Then open `http://127.0.0.1:8737/` in Safari and choose **File → Add to Dock** to get the app icon.

Run it without the login service: `/usr/bin/python3 server.py`. Remove the service: `./uninstall.sh`.

## OBS

1. **Sources → + → Browser**, URL `http://127.0.0.1:8737/view`, sized to match the quality (for example 1920×1080).
2. To line up game footage with the camera, press **Measure delay** in Phone Cam (point the phone at the screen). Then:
   - add **Render Delay** filters to the game capture that add up to the measured delay (each one is limited to 500 ms);
   - set the game audio's **Sync Offset** in Edit → Advanced Audio Properties to the same value.

## Files

| File | Purpose |
| --- | --- |
| `server.py` | Starts the camera stream and serves the UI, `/view`, `/stream` (MJPEG), `/snapshot.jpg` and `/api/*` |
| `ui.html` | Control app |
| `view.html` | The OBS page: picture only |
| `install.sh` / `uninstall.sh` | Login service (LaunchAgent) |
| `start.sh` | Starts the server if needed and opens the UI |
| `tools/make-icon.swift` | Regenerates `icon.png` |

## License

MIT
