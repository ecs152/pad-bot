import AppKit
import SwiftUI

/// `PADBot --snapshot DIR`: renders each panel offscreen to DIR/<id>.png with sample data, then exits.
/// Used to review UI changes without opening a window.
enum Snapshot {
    @MainActor
    static func renderAll(to dir: String) {
        _ = NSApplication.shared
        let bot = BotRunner()
        let sample = [
            "screen: list", "  list: tap 'Genie of the Lamp'", "screen: helper", "  helper: tap 'You'",
            "screen: enter", "  enter: tap 'Enter'", "turn 0: mechanics=[] counters=[]", "  skill slot 1",
            "  board RBGRBG / BGDGRB / GDLDBR / RBDRGB / BGDBRG  route [(2, 2), (3, 2)]", "  drag 1 steps",
        ]
        sample.forEach { bot.handle($0) }
        bot.handle(#"@ev {"type":"start","live":false,"runs":3}"#)
        bot.handle(#"@ev {"type":"screen","name":"battle_ready"}"#)
        bot.handle(#"@ev {"type":"turn","turn":2,"board":[],"route":[]}"#)
        bot.handle(#"@ev {"type":"cleared","count":1,"runs":3}"#)
        bot.running = true
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        for p in panels {
            save(p.view(bot).environmentObject(bot).padding().frame(width: 520, height: 600).background(Color(nsColor: .windowBackgroundColor)), "\(dir)/\(p.id).png")
        }
    }

    @MainActor
    static func save<V: View>(_ v: V, _ path: String) {
        let host = NSHostingView(rootView: v)
        host.frame = NSRect(x: 0, y: 0, width: 520, height: 600)
        let win = NSWindow(contentRect: host.frame, styleMask: [.titled], backing: .buffered, defer: false)
        win.contentView = host
        host.layoutSubtreeIfNeeded()
        let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds)!
        host.cacheDisplay(in: host.bounds, to: rep)
        try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: path))
    }
}
