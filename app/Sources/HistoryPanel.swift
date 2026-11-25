import SwiftUI

/// One finished run: a line of logs/history.jsonl or a live `run` event (see docs/events.md).
struct RunRecord: Identifiable {
    let id = UUID()
    let t: Double
    let target: String
    let cleared: Bool
    let seconds: Double
    let stamina: String
    let coins: String
    let drops: String
    let reason: String

    init(_ d: [String: Any]) {
        t = d["t"] as? Double ?? 0
        target = d["target"] as? String ?? "?"
        cleared = d["result"] as? String == "cleared"
        seconds = d["seconds"] as? Double ?? 0
        let st = d["stamina"] as? [Int] ?? []
        stamina = st.count == 2 ? "\(st[0])/\(st[1])" : "–"
        coins = (d["coins"] as? Int).map { $0.formatted() } ?? "–"
        drops = (d["drops"] as? [Any]).map { $0.isEmpty ? "none" : "\($0.count)" } ?? "–"
        reason = d["reason"] as? String ?? ""
    }

    var time: String { Date(timeIntervalSince1970: t).formatted(.dateTime.month(.defaultDigits).day().hour().minute()) }
    var duration: String { String(format: "%d:%02d", Int(seconds) / 60, Int(seconds) % 60) }
}

/// Every run the bot finished or was stopped in, newest first, with why it stopped.
struct HistoryPanel: View {
    @EnvironmentObject var bot: BotRunner
    @State private var saved: [RunRecord] = []

    static var file: URL { BotRunner.root.appendingPathComponent("logs/history.jsonl") }

    /// Saved history plus this session's `run` events not yet loaded from the file.
    private var records: [RunRecord] {
        let last = saved.last?.t ?? 0
        let live = bot.events.filter { $0.type == "run" && ($0.data["t"] as? Double ?? 0) > last }.map { RunRecord($0.data) }
        return (saved + live).reversed()
    }

    var body: some View {
        let r = records
        let clears = r.filter(\.cleared)
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(clears.count == 1 ? "1 clear" : "\(clears.count) clears").font(.headline)
                if !clears.isEmpty {
                    let avg = clears.map(\.seconds).reduce(0, +) / Double(clears.count)
                    Text("· \(String(format: "%d:%02d", Int(avg) / 60, Int(avg) % 60)) per clear on average")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button { load() } label: { Image(systemName: "arrow.clockwise") }.help("Reload history")
            }
            if let s = r.first(where: { !$0.cleared }) {
                Label("Last stop: \(s.reason)", systemImage: "exclamationmark.octagon")
                    .font(.callout).foregroundStyle(.orange).lineLimit(3)
            }
            List(r) { x in
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Image(systemName: x.cleared ? "checkmark.circle.fill" : "stop.circle.fill")
                            .foregroundStyle(x.cleared ? Color.green : Color.orange)
                        Text(x.target).lineLimit(1)
                        Spacer()
                        Text(x.time).foregroundStyle(.secondary)
                    }
                    Text(x.cleared ? "\(x.duration) · stamina \(x.stamina) · \(x.coins) coins · drops: \(x.drops)"
                                   : "\(x.reason) (after \(x.duration))")
                        .font(.caption).foregroundStyle(.secondary).lineLimit(2)
                }
            }
            if r.isEmpty {
                Text("No runs yet. Finished and stopped runs show up here.").foregroundStyle(.secondary)
            }
        }
        .onAppear(perform: load)
    }

    private func load() {
        guard let text = try? String(contentsOf: Self.file, encoding: .utf8) else { saved = []; return }
        saved = text.split(separator: "\n").compactMap {
            (try? JSONSerialization.jsonObject(with: Data($0.utf8))) as? [String: Any]
        }.map(RunRecord.init)
    }
}
