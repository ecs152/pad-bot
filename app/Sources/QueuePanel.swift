import SwiftUI

/// One queue target: a dungeon/floor path, or "uncleared floors" (which skips the dungeons in config nav.skip).
struct QueueItem: Codable, Identifiable, Equatable {
    var id = UUID()
    var uncleared = false
    var path = ""
    var runs = 1

    var valid: Bool { uncleared || path.split(separator: "/").filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }.count >= 2 }
}

/// Runs a list of targets in order (`run --queue`). Shows where the queue is and the stamina read off the screen.
struct QueuePanel: View {
    @EnvironmentObject var bot: BotRunner
    /// Snapshot swaps in a scratch store so its sample queue never replaces the user's.
    static var store = UserDefaults.standard
    @AppStorage("queue", store: QueuePanel.store) private var stored = "[]"
    @AppStorage("practice") private var practice = true
    @AppStorage("maxRuns") private var maxRuns = 20
    @AppStorage("extraStopWords") private var extraStopWords = ""
    @AppStorage("profile") private var profile = "profiles/lugner.toml"  // team picked on the Run tab
    @State private var items: [QueueItem] = []
    @State private var confirmLive = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            List {
                ForEach($items) { $item in
                    HStack {
                        Picker("", selection: $item.uncleared) {
                            Text("Floor").tag(false)
                            Text("Uncleared").tag(true)
                        }
                        .labelsHidden().fixedSize()
                        if item.uncleared {
                            Text("Uncleared floors, skipping Aither Desert").foregroundStyle(.secondary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        } else {
                            TextField("Dungeon/Floor", text: $item.path, prompt: Text("Dungeon name/Floor name"))
                                .foregroundStyle(item.valid ? Color.primary : Color.red)
                        }
                        Stepper("× \(item.runs)", value: $item.runs, in: 1...max(1, maxRuns)).fixedSize()
                        Button { items.removeAll { $0.id == item.id } } label: { Image(systemName: "minus.circle") }
                            .buttonStyle(.borderless)
                    }
                    .listRowBackground(rowColor(item))
                }
                .onMove { items.move(fromOffsets: $0, toOffset: $1) }
            }
            .frame(minHeight: 160)
            .disabled(bot.running)

            HStack {
                Button { items.append(QueueItem(uncleared: items.isEmpty)) } label: { Label("Add target", systemImage: "plus") }
                Spacer()
                Text("Drag to reorder. \(planned.reduce(0) { $0 + $1.runs }) runs (max \(maxRuns))")
                    .font(.caption).foregroundStyle(.secondary)
            }
            .disabled(bot.running)

            Toggle("Practice run (reads and plans, no taps)", isOn: $practice).disabled(bot.running)

            HStack {
                if bot.running {
                    Button(role: .destructive) { bot.stop() } label: { Label("Stop", systemImage: "stop.fill") }
                } else {
                    Button { practice ? start() : (confirmLive = true) } label: {
                        Label(practice ? "Start queue (practice)" : "Start queue live", systemImage: "play.fill")
                    }
                    .disabled(planned.isEmpty || !items.allSatisfy(\.valid))
                }
                Spacer()
                if let s = stamina { Label("Stamina \(s)", systemImage: "bolt.fill").font(.callout) }
            }
            .controlSize(.large)

            if let p = position { Text(p).font(.callout) }
            Text(bot.status).font(.callout).foregroundStyle(.secondary).lineLimit(2)
        }
        .onAppear { items = (try? JSONDecoder().decode([QueueItem].self, from: Data(stored.utf8))) ?? [] }
        .onChange(of: items) { _, v in
            if let d = try? JSONEncoder().encode(v) { stored = String(decoding: d, as: UTF8.self) }
        }
        .confirmationDialog("Start a live queue?", isPresented: $confirmLive) {
            Button("Start live") { start() }
        } message: {
            Text("The bot will tap and drag in iPhone Mirroring and control your mouse for every target in the queue. To stop it, move the mouse to the top-left corner of the screen, or use Stop in the menu bar.")
        }
    }

    /// Items capped so the whole queue stays within Safety's "Max runs per start".
    private var planned: [QueueItem] {
        var left = maxRuns
        return items.compactMap { i in
            let n = min(i.runs, left)
            left -= n
            return n > 0 ? QueueItem(id: i.id, uncleared: i.uncleared, path: i.path, runs: n) : nil
        }
    }

    private var lastQueueEvent: BotEvent? { bot.events.last { $0.type == "queue" } }

    private var position: String? {
        guard bot.running, let e = lastQueueEvent, let i = e.data["index"] as? Int, let n = e.data["of"] as? Int else { return nil }
        return "Target \(i + 1) of \(n): \(e.data["target"] as? String ?? "?")"
    }

    private var stamina: String? {
        guard let e = bot.events.last(where: { $0.type == "stamina" }),
              let now = e.data["now"] as? Int, let max = e.data["max"] as? Int else { return nil }
        return "\(now)/\(max)"
    }

    private func rowColor(_ item: QueueItem) -> Color? {
        guard bot.running, let i = lastQueueEvent?.data["index"] as? Int,
              let idx = planned.firstIndex(where: { $0.id == item.id }), idx == i else { return nil }
        return Color.accentColor.opacity(0.15)
    }

    private func start() {
        let q: [[String: Any]] = planned.map { $0.uncleared ? ["uncleared": true, "runs": $0.runs] : ["path": $0.path, "runs": $0.runs] }
        guard let d = try? JSONSerialization.data(withJSONObject: q) else { return }
        var args = ["--queue", String(decoding: d, as: UTF8.self)]
        if !practice { args.append("--live") }
        if !extraStopWords.isEmpty { args += ["--stop-words", extraStopWords] }
        args += ["--profile", profile]
        bot.start(args: args)
    }
}
