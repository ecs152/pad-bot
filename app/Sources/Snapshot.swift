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
        bot.handle(#"@ev {"type":"turn","turn":2,"board":["BDGBHB","DDDBDL","BDLLDR","RRDDBH","BRBLGH"],"route":[[2,4],[3,4],[3,5]],"goal":{"crosses":{"D":1}},"mechanics":[]}"#)
        bot.handle(#"@ev {"type":"cleared","count":1,"runs":3}"#)
        bot.running = true
        InfoLookup.shared.handle(InfoLookup.sample)
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

/// `PADBot --selftest REPLAYDIR`: starts the bot on saved screenshots (no window capture, no taps), presses
/// Stop after 4 s, and exits 0 only if events arrived and the bot reported the stop and exited.
enum SelfTest {
    static func run(replay: String) -> Never {
        let bot = BotRunner()
        bot.start(args: ["--replay", replay, "--uncleared"])
        let t0 = Date()
        var stopped = false
        while Date().timeIntervalSince(t0) < 20 {
            RunLoop.main.run(until: Date().addingTimeInterval(0.1))
            if !stopped && Date().timeIntervalSince(t0) > 4 { bot.stop(); stopped = true }
            if stopped && !bot.running { break }
        }
        let types = Set(bot.events.map(\.type))
        print("events:", types.sorted(), "running:", bot.running, "status:", bot.status)
        exit(types.contains("start") && types.contains("screen") && bot.stopReason == "Stopped by user" && !bot.running ? 0 : 1)
    }
}
