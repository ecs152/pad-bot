import AppKit
import Foundation

/// One `@ev {json}` line from the bot. `data` holds the event's fields (see docs/events.md).
struct BotEvent: Identifiable {
    let id = UUID()
    let type: String
    let data: [String: Any]
}

/// Runs `python -m padbot run ...` from the repo and turns its output into published state.
final class BotRunner: ObservableObject {
    @Published var running = false
    @Published var live = false
    @Published var screen = ""
    @Published var turn = 0
    @Published var cleared = 0
    @Published var runs = 0
    @Published var stopReason: String?
    @Published var log: [String] = []
    @Published var events: [BotEvent] = []
    @Published var lastTurn: BotEvent?

    private var process: Process?
    private var buffer = Data()

    /// Repo folder: written into Info.plist by app/build.sh.
    static let root: URL = {
        let p = Bundle.main.object(forInfoDictionaryKey: "PadBotRoot") as? String
        return URL(fileURLWithPath: p ?? FileManager.default.currentDirectoryPath)
    }()

    var status: String {
        if running {
            return "\(live ? "Live" : "Practice"): \(screen.isEmpty ? "starting" : screen.replacingOccurrences(of: "_", with: " ")), turn \(turn), cleared \(cleared)/\(runs)"
        }
        if let r = stopReason { return "Stopped: \(r)" }
        return cleared > 0 ? "Done: \(cleared) clear(s)" : "Idle"
    }

    func start(args: [String]) {
        guard !running else { return }
        let p = Process()
        p.executableURL = Self.root.appendingPathComponent(".venv/bin/python")
        p.arguments = ["-u", "-m", "padbot", "run"] + args
        p.currentDirectoryURL = Self.root
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] h in
            let d = h.availableData
            DispatchQueue.main.async { self?.consume(d) }
        }
        p.terminationHandler = { [weak self] proc in
            DispatchQueue.main.async { self?.finished(proc.terminationStatus) }
        }
        (events, log, screen, turn, cleared, stopReason, lastTurn) = ([], [], "", 0, 0, nil, nil)
        do {
            try p.run()
        } catch {
            stopReason = "couldn't start the bot (\(error.localizedDescription))"
            return
        }
        process = p
        running = true
    }

    /// SIGINT: the bot stops at once and releases the mouse if it was mid-drag.
    func stop() { process?.interrupt() }

    private func consume(_ d: Data) {
        buffer.append(d)
        while let nl = buffer.firstIndex(of: 0x0A) {
            let line = String(decoding: buffer[..<nl], as: UTF8.self)
            buffer.removeSubrange(...nl)
            handle(line)
        }
    }

    func handle(_ line: String) {
        guard line.hasPrefix("@ev "),
              let obj = try? JSONSerialization.jsonObject(with: Data(line.dropFirst(4).utf8)) as? [String: Any],
              let type = obj["type"] as? String
        else {
            log.append(line)
            if log.count > 3000 { log.removeFirst(500) }
            return
        }
        let e = BotEvent(type: type, data: obj)
        events.append(e)
        switch type {
        case "start":
            live = obj["live"] as? Bool ?? false
            runs = obj["runs"] as? Int ?? 0
        case "screen": screen = obj["name"] as? String ?? ""
        case "turn":
            turn = obj["turn"] as? Int ?? turn
            lastTurn = e
        case "cleared": cleared = obj["count"] as? Int ?? cleared
        case "stop":
            stopReason = obj["reason"] as? String ?? "unknown"
            alert()
        default: break
        }
    }

    private func finished(_ code: Int32) {
        running = false
        process = nil
        if code != 0 && stopReason == nil { stopReason = "bot exited with code \(code)" }
    }

    /// "Alert me when it needs me" (Safety): sound + bouncing Dock icon. The bot also posts a Mac notification.
    private func alert() {
        guard UserDefaults.standard.bool(forKey: "alertOnStop") else { return }
        NSSound(named: "Funk")?.play()
        NSApp.requestUserAttention(.criticalRequest)
    }
}
