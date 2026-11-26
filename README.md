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

## Troubleshooting

**"Phone not found" / the device line says no phone**
- Use a data cable (some cables only charge) and plug it straight into the Mac, not through a hub.
- Run `adb devices`. The phone should be listed as `device`.
- If the phone keeps disconnecting as soon as the camera starts, try another cable or port. The camera draws extra power.

**The phone shows `unauthorized` in `adb devices`, or the app says "tap Allow"**
- Unlock the phone and accept **Allow USB debugging?** Tick **Always allow from this computer**.
- No prompt? Run `adb usb` (this restarts USB debugging on the phone and brings the prompt back), or unplug and replug.
- Still nothing? On the phone, go to **Developer options → Revoke USB debugging authorizations** and replug.

**"The phone did not send any video"**
- Another app may be using the camera. Close the phone's Camera app and stop any other scrcpy session.
- Press **Stop**, then **Start** again. If that fails, unplug and replug.
- The camera source needs **Android 12 or newer**. Check with `adb shell getprop ro.build.version.release`.

**OBS shows black, or a frozen picture**
- Check that the Phone Cam app says **Live**. The OBS page shows nothing while the camera is off, and picks up again by itself when you press Start.
- Check that the Browser source URL is exactly `http://127.0.0.1:8737/view`.
- Right-click the source and choose **Refresh**, or tick **Refresh browser when scene becomes active** in its properties.
- Make sure the server is running: `curl http://127.0.0.1:8737/api/status`. If not, run `./install.sh` again, or check `server.log`.

**Low frame rate or more delay than usual**
- In a dark room the phone lowers its frame rate to expose longer, so add light.
- 4K costs more than 1080p. Measure the delay again after changing quality or lighting, and update the OBS Render Delay to match.

**Picture is upside down or sideways**
- Use **Rotate** in the app. If you pick 90° or 270°, set the OBS Browser source size to portrait (for example 1080×1920).

**Port 8737 is already in use**
- Another copy is running. Run `./uninstall.sh`, then `./install.sh` (or `lsof -iTCP:8737` to see what holds the port).

**The phone has no Wi-Fi or internet**
- That's fine: Phone Cam only needs the USB cable.
- If the phone ever needs internet (for example to install something), [gnirehtet](https://github.com/Genymobile/gnirehtet) can share the Mac's connection over USB (`brew install gnirehtet`). Note that the Play Store usually won't download over it: it waits for a "real" network.

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
