// Phone Cam menu bar icon: a small "p" that turns red while the camera is live.
// Build: tools/build-menubar.sh
import Cocoa

let base = "http://127.0.0.1:8737"

final class App: NSObject, NSApplicationDelegate {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
    let menu = NSMenu()
    let stateLine = NSMenuItem(title: "Checking…", action: nil, keyEquivalent: "")
    let toggle = NSMenuItem(title: "Start camera", action: #selector(toggleCam), keyEquivalent: "")
    var state = "unknown"
    var settings: [String: Any] = [:]

    func applicationDidFinishLaunching(_ n: Notification) {
        stateLine.isEnabled = false
        toggle.target = self
        menu.addItem(stateLine)
        menu.addItem(.separator())
        menu.addItem(toggle)
        menu.addItem(withTitle: "Open Phone Cam", action: #selector(openUI), keyEquivalent: "o").target = self
        menu.addItem(withTitle: "Copy OBS link", action: #selector(copyLink), keyEquivalent: "c").target = self
        menu.addItem(.separator())
        menu.addItem(withTitle: "Hide menu bar icon", action: #selector(quit), keyEquivalent: "q").target = self
        item.menu = menu
        paint()
        poll()
        Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in self?.poll() }
    }

    func icon(live: Bool) -> NSImage {
        let s: CGFloat = 18
        let img = NSImage(size: NSSize(width: s, height: s), flipped: false) { r in
            let box = r.insetBy(dx: 1.5, dy: 1.5)
            let font = NSFont.systemFont(ofSize: 13, weight: .bold)
            let color: NSColor = live ? .white : .black
            if live {
                NSColor.systemRed.setFill()
                NSBezierPath(ovalIn: box).fill()
            } else {
                let p = NSBezierPath(roundedRect: box, xRadius: 4, yRadius: 4)
                p.lineWidth = 1.4
                NSColor.black.setStroke()
                p.stroke()
            }
            let str = NSAttributedString(string: "p", attributes: [.font: font, .foregroundColor: color])
            let sz = str.size()
            str.draw(at: NSPoint(x: r.midX - sz.width / 2, y: r.midY - sz.height / 2 + 1.5))
            return true
        }
        img.isTemplate = !live   // off: follows light/dark menu bar; live: stays red
        return img
    }

    func paint() {
        let live = state == "live" || state == "starting"
        item.button?.image = icon(live: live)
        item.button?.toolTip = live ? "Phone Cam: LIVE" : "Phone Cam"
        switch state {
        case "live": stateLine.title = "🔴 Camera is live"
        case "starting": stateLine.title = "🔴 Camera is starting…"
        case "off": stateLine.title = "Camera is off"
        case "error": stateLine.title = "Camera error (open Phone Cam)"
        case "down": stateLine.title = "Phone Cam server is not running"
        default: stateLine.title = "Checking…"
        }
        toggle.title = live ? "Stop camera" : "Start camera"
        toggle.isEnabled = state != "down" && state != "unknown"
    }

    func request(_ path: String, body: [String: Any]? = nil) {
        var req = URLRequest(url: URL(string: base + path)!, timeoutInterval: 3)
        if let body = body {
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        }
        URLSession.shared.dataTask(with: req) { [weak self] data, _, err in
            var st = "down"
            var set: [String: Any]? = nil
            if err == nil, let d = data, let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
                st = j["state"] as? String ?? "off"
                set = j["settings"] as? [String: Any]
            }
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.state = st
                if let set = set { self.settings = set }
                self.paint()
            }
        }.resume()
    }

    func poll() { request("/api/status") }

    @objc func toggleCam() {
        if state == "live" || state == "starting" { request("/api/stop", body: [:]) }
        else { request("/api/start", body: settings) }
    }

    @objc func openUI() {
        let app = URL(fileURLWithPath: NSHomeDirectory() + "/Applications/Phone Cam.app")
        if FileManager.default.fileExists(atPath: app.path) { NSWorkspace.shared.open(app) }
        else { NSWorkspace.shared.open(URL(string: base + "/")!) }
    }

    @objc func copyLink() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(base + "/view", forType: .string)
    }

    @objc func quit() { NSApp.terminate(nil) }
}

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
