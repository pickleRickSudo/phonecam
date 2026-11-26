#!/usr/bin/env python3
"""Phone Cam: streams an Android phone camera (via scrcpy over USB) to a local
MJPEG URL that OBS can load as a Browser source. Stdlib only."""
import json
import os
import shutil
import glob
import signal
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8737
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")
SCRCPY = shutil.which("scrcpy")
FFMPEG = shutil.which("ffmpeg")
ADB = shutil.which("adb")
# scrcpy's phone-side server; its version must match the one we tell it.
_jars = sorted(glob.glob("/opt/homebrew/Cellar/scrcpy/*/share/scrcpy/scrcpy-server"))
SERVER_JAR = _jars[-1] if _jars else ""
SCRCPY_VERSION = SERVER_JAR.split("/scrcpy/")[1].split("/")[0] if SERVER_JAR else ""
PHONE_JAR = "/data/local/tmp/phonecam-server.jar"

QUALITY = {  # name -> (size, scrcpy bitrate, jpeg q: 2 best .. 31 worst)
    "720p": ("1280x720", "8M", 4),
    "1080p": ("1920x1080", "16M", 3),
    "4k": ("3840x2160", "40M", 3),
}
CAMERAS = {"back": "0", "back2": "2", "front": "1", "front2": "3"}
DEFAULTS = {"camera": "back", "quality": "1080p", "fps": 30, "rotate": 0}


class Cam:
    def __init__(self):
        self.lock = threading.Lock()
        self.cond = threading.Condition()
        self.frame = None
        self.frame_no = 0
        self.state = "off"  # off | starting | live | error
        self.error = ""
        self.settings = dict(DEFAULTS)
        self.procs = []
        self.port = None
        self.sock = None
        self.fps = 0.0
        self.gen = 0
        self._load()

    def _load(self):
        try:
            with open(os.path.join(HERE, "settings.json")) as f:
                self.settings.update(json.load(f))
        except Exception:
            pass

    def _save(self):
        try:
            with open(os.path.join(HERE, "settings.json"), "w") as f:
                json.dump(self.settings, f)
        except Exception:
            pass

    def start(self, s):
        self.stop()
        s = {**self.settings, **(s or {})}
        if s.get("camera") not in CAMERAS:
            s["camera"] = "back"
        if s.get("quality") not in QUALITY:
            s["quality"] = "1080p"
        s["fps"] = 24 if int(s.get("fps", 30)) == 24 else 30
        s["rotate"] = int(s.get("rotate", 0)) if int(s.get("rotate", 0)) in (0, 90, 180, 270) else 0
        self.settings = s
        self._save()
        size, bitrate, q = QUALITY[s["quality"]]
        with self.lock:
            self.gen += 1
            gen = self.gen
            self.state, self.error, self.fps = "starting", "", 0.0
        threading.Thread(target=self._launch, args=(gen, s, size, bitrate, q), daemon=True).start()

    def _fail(self, gen, msg):
        with self.cond:
            if gen == self.gen:
                self.state, self.error, self.frame = "error", msg, None
                self.cond.notify_all()

    def _launch(self, gen, s, size, bitrate, q):
        # Runs scrcpy's phone-side server directly in raw H.264 mode (no window,
        # no container buffering), then turns it into MJPEG with ffmpeg.
        dev = device_info(fresh=True)
        if dev["state"] != "device":
            return self._fail(gen, "Phone not found or not authorized. Check the USB cable and tap Allow on the phone.")
        subprocess.run([ADB, "push", SERVER_JAR, PHONE_JAR], capture_output=True, timeout=20)
        scid = "%08x" % (int(time.time() * 1000) & 0x7FFFFFFF)
        with socket.socket() as t:
            t.bind(("127.0.0.1", 0))
            port = t.getsockname()[1]
        subprocess.run([ADB, "forward", f"tcp:{port}", f"localabstract:scrcpy_{scid}"],
                       capture_output=True, timeout=10)
        srv_args = [f"scid={scid}", "log_level=info", "tunnel_forward=true", "audio=false",
                    "control=false", "raw_stream=true", "video_source=camera",
                    f"camera_id={CAMERAS[s['camera']]}", f"camera_size={size}",
                    f"camera_fps={s['fps']}", f"video_bit_rate={bitrate[:-1]}000000"]
        sh = subprocess.Popen([ADB, "shell", f"CLASSPATH={PHONE_JAR}", "app_process", "/",
                               "com.genymobile.scrcpy.Server", SCRCPY_VERSION] + srv_args,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, start_new_session=True)
        log = []
        threading.Thread(target=self._read_log, args=(sh, log), daemon=True).start()
        with self.lock:
            if gen != self.gen:
                return self._kill([sh], port)
            self.procs, self.port = [sh], port
        sock, first, t0 = None, b"", time.time()
        while time.time() - t0 < 12 and gen == self.gen:
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=2)
                sock.settimeout(3)
                first = sock.recv(65536)
                if first:
                    break
            except OSError:
                pass
            if sock:
                sock.close()
                sock = None
            if sh.poll() is not None:
                break
            time.sleep(0.3)
        if not first:
            if sock:
                sock.close()
            msg = " / ".join([l for l in log if "ERROR" in l or "Exception" in l][-2:]) or \
                "The phone did not send any video. Unplug and replug the cable, then try again."
            return self._fail(gen, msg)
        sock.settimeout(None)
        # Decoder: 1 thread + low_delay, so frames come out as soon as they arrive
        # (frame-threading holds several frames back and adds a lot of delay).
        ff_cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-probesize", "32",
                  "-analyzeduration", "0", "-threads", "1", "-flags", "low_delay",
                  "-f", "h264", "-i", "pipe:0", "-an",
                  "-fps_mode", "passthrough"]
        if s["rotate"]:
            ff_cmd += ["-vf", {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}[s["rotate"]]]
        ff_cmd += ["-c:v", "mjpeg", "-pix_fmt", "yuvj420p", "-q:v", str(q), "-flush_packets", "1",
                   "-f", "mjpeg", "pipe:1"]
        ff = subprocess.Popen(ff_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, start_new_session=True)
        with self.lock:
            if gen != self.gen:
                sock.close()
                return self._kill([sh, ff], port)
            self.procs = [sh, ff]
            self.sock = sock
        threading.Thread(target=self._pump, args=(sock, ff, first), daemon=True).start()
        self._read_frames(ff, gen, log)

    def _pump(self, sock, ff, first):
        try:
            ff.stdin.write(first)
            while True:
                d = sock.recv(262144)
                if not d:
                    break
                ff.stdin.write(d)
                ff.stdin.flush()
        except Exception:
            pass
        try:
            ff.stdin.close()
        except Exception:
            pass

    def _read_log(self, p, log):
        for line in iter(p.stdout.readline, b""):
            log.append(line.decode(errors="replace").rstrip())
            del log[:-20]

    def _read_frames(self, ff, gen, log):
        buf = b""
        count, t0 = 0, time.time()
        while True:
            chunk = ff.stdout.read(65536)
            if not chunk:
                break
            buf += chunk
            while True:
                a = buf.find(b"\xff\xd8")
                if a < 0:
                    buf = b""
                    break
                b = buf.find(b"\xff\xd9", a + 2)
                if b < 0:
                    buf = buf[a:]
                    break
                jpg, buf = buf[a:b + 2], buf[b + 2:]
                with self.cond:
                    if gen != self.gen:
                        return
                    self.frame = jpg
                    self.frame_no += 1
                    self.state = "live"
                    self.cond.notify_all()
                count += 1
                now = time.time()
                if now - t0 >= 1:
                    self.fps, count, t0 = count / (now - t0), 0, now
        err = (ff.stderr.read() or b"").decode(errors="replace").strip()
        with self.cond:
            if gen == self.gen and self.state in ("starting", "live"):
                self.state = "error"
                lines = [l for l in log if "WARN" in l or "ERROR" in l] or log[-3:]
                msg = " / ".join(lines[-3:]) or err[-300:]
                if "disconnected" in msg.lower() or "no device" in msg.lower() or "could not find" in msg.lower():
                    msg = "Phone disconnected or not authorized. Check the USB cable, then press Start again."
                self.error = msg or "Camera stream stopped."
                self.frame = None
                self.cond.notify_all()

    def stop(self):
        with self.cond:
            self.gen += 1
            self.state, self.frame, self.fps, self.error = "off", None, 0.0, ""
            self.cond.notify_all()
            procs, port, sock = self.procs, self.port, self.sock
            self.procs, self.port, self.sock = [], None, None
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        self._kill(procs, port)

    def _kill(self, procs, port):
        for p in procs:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=3)
            except Exception:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except Exception:
                    pass
        if procs or port:  # make sure the phone releases the camera
            subprocess.run([ADB, "shell", "pkill", "-f", "com.genymobile.scrcpy.Server"],
                           capture_output=True, timeout=5)
        if port:
            subprocess.run([ADB, "forward", "--remove", f"tcp:{port}"], capture_output=True, timeout=5)

    def status(self):
        return {"state": self.state, "error": self.error, "settings": self.settings,
                "fps": round(self.fps, 1), "device": device_info(),
                "view_url": f"http://{HOST}:{PORT}/view"}


_dev_cache = {"t": 0, "v": None}


def device_info(fresh=False):
    if not fresh and time.time() - _dev_cache["t"] < 3:
        return _dev_cache["v"]
    v = {"state": "none", "model": ""}
    try:
        out = subprocess.run([ADB, "devices", "-l"], capture_output=True, text=True, timeout=4).stdout
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                v["state"] = parts[1]
                for p in parts:
                    if p.startswith("model:"):
                        v["model"] = p[6:].replace("_", "-")
                break
    except Exception:
        v["state"] = "adb-missing"
    _dev_cache.update(t=time.time(), v=v)
    return v


CAM = Cam()
SERVER = None


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name, ctype):
        with open(os.path.join(HERE, name), "rb") as f:
            self._send(200, f.read(), ctype)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            return self._file("ui.html", "text/html; charset=utf-8")
        if path == "/view":
            return self._file("view.html", "text/html; charset=utf-8")
        if path in ("/icon.png", "/apple-touch-icon.png"):
            return self._file("icon.png", "image/png")
        if path == "/manifest.json":
            return self._send(200, json.dumps({
                "name": "Phone Cam", "short_name": "Phone Cam", "start_url": "/", "display": "standalone",
                "background_color": "#141414", "theme_color": "#f26b3a",
                "icons": [{"src": "/icon.png", "sizes": "1024x1024", "type": "image/png"}]}),
                "application/manifest+json")
        if path == "/api/status":
            return self._send(200, json.dumps(CAM.status()), "application/json")
        if path == "/snapshot.jpg":
            f = CAM.frame
            return self._send(200, f, "image/jpeg") if f else self._send(404, "no frame", "text/plain")
        if path == "/stream":
            return self._stream()
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            data = {}
        path = self.path.split("?")[0]
        if path == "/api/start":
            CAM.start(data)
        elif path == "/api/stop":
            CAM.stop()
        elif path == "/api/quit":
            self._send(200, "{}", "application/json")
            threading.Thread(target=shutdown, daemon=True).start()
            return
        else:
            return self._send(404, "{}", "application/json")
        self._send(200, json.dumps(CAM.status()), "application/json")

    def _stream(self):
        # Keeps the connection open even while the camera is off, so OBS picks
        # the picture back up by itself as soon as you press Start again.
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        last = -1
        try:
            while True:
                with CAM.cond:
                    CAM.cond.wait_for(lambda: CAM.frame_no != last and CAM.frame is not None, timeout=5)
                    f, last = CAM.frame, CAM.frame_no
                if f is None:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                 + str(len(f)).encode() + b"\r\n\r\n" + f + b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


def shutdown():
    CAM.stop()
    time.sleep(0.2)
    SERVER.shutdown()


if __name__ == "__main__":
    for tool, name in ((SERVER_JAR, "scrcpy"), (FFMPEG, "ffmpeg"), (ADB, "adb")):
        if not tool:
            raise SystemExit(f"{name} not found; install it with Homebrew.")
    SERVER = ThreadingHTTPServer((HOST, PORT), H)
    SERVER.daemon_threads = True
    signal.signal(signal.SIGTERM, lambda *a: threading.Thread(target=shutdown, daemon=True).start())
    print(f"Phone Cam on http://{HOST}:{PORT}/", flush=True)
    try:
        SERVER.serve_forever()
    finally:
        CAM.stop()
