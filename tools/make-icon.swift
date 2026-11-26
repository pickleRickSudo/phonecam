import AppKit
let size = 1024.0
let img = NSImage(size: NSSize(width: size, height: size))
img.lockFocus()
let rect = NSRect(x: 100, y: 100, width: 824, height: 824)
let path = NSBezierPath(roundedRect: rect, xRadius: 185, yRadius: 185)
NSGradient(starting: NSColor(calibratedRed: 1.00, green: 0.62, blue: 0.22, alpha: 1),
           ending: NSColor(calibratedRed: 0.93, green: 0.30, blue: 0.24, alpha: 1))!.draw(in: path, angle: -90)
let cfg = NSImage.SymbolConfiguration(pointSize: 560, weight: .semibold)
if let sym = NSImage(systemSymbolName: "iphone.rear.camera", accessibilityDescription: nil)?.withSymbolConfiguration(cfg) {
  let tinted = NSImage(size: sym.size); tinted.lockFocus()
  sym.draw(at: .zero, from: .zero, operation: .sourceOver, fraction: 1)
  NSColor.white.set(); NSRect(origin: .zero, size: sym.size).fill(using: .sourceAtop); tinted.unlockFocus()
  tinted.draw(in: NSRect(x: (size - sym.size.width)/2, y: (size - sym.size.height)/2, width: sym.size.width, height: sym.size.height))
}
img.unlockFocus()
let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
