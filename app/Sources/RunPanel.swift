import SwiftUI

struct RunPanel: View {
    @EnvironmentObject var bot: BotRunner
    @AppStorage("uncleared") private var uncleared = true
    @AppStorage("path") private var path = ""
    @AppStorage("runs") private var runs = 1
    @AppStorage("practice") private var practice = true
    @AppStorage("maxRuns") private var maxRuns = 20
    @AppStorage("extraStopWords") private var extraStopWords = ""
    @State private var confirmLive = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Form {
                Picker("Play", selection: $uncleared) {
                    Text("Uncleared floors").tag(true)
                    Text("Dungeon and floor").tag(false)
                }
                .pickerStyle(.segmented)
                if !uncleared {
                    TextField("Dungeon/Floor", text: $path, prompt: Text("Dungeon name/Floor name"))
                }
                Stepper("Runs: \(min(runs, maxRuns))", value: $runs, in: 1...max(1, maxRuns))
                Toggle("Practice run (reads and plans, no taps)", isOn: $practice)
            }
            .disabled(bot.running)

            HStack {
                if bot.running {
                    Button(role: .destructive) { bot.stop() } label: { Label("Stop", systemImage: "stop.fill") }
                        .keyboardShortcut(".", modifiers: .command)
                } else {
                    Button { practice ? start() : (confirmLive = true) } label: {
                        Label(practice ? "Start practice" : "Start live", systemImage: "play.fill")
                    }
                    .keyboardShortcut(.return, modifiers: .command)
                    .disabled(!uncleared && !path.contains("/"))
                }
                Spacer()
                Circle().fill(bot.running ? (bot.live ? Color.red : Color.orange) : Color.secondary)
                    .frame(width: 8, height: 8)
                Text(bot.status).font(.callout).lineLimit(2)
            }
            .controlSize(.large)

            LogView(lines: bot.log)
        }
        .confirmationDialog("Start a live run?", isPresented: $confirmLive) {
            Button("Start live") { start() }
        } message: {
            Text("The bot will tap and drag in iPhone Mirroring and control your mouse. To stop it, move the mouse to the top-left corner of the screen, or use Stop in the menu bar.")
        }
    }

    private func start() {
        var args = uncleared ? ["--uncleared"] : ["--path", path]
        args += ["--runs", String(min(runs, maxRuns))]
        if !practice { args.append("--live") }
        if !extraStopWords.isEmpty { args += ["--stop-words", extraStopWords] }
        bot.start(args: args)
    }
}

struct LogView: View {
    let lines: [String]

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 1) {
                    ForEach(Array(lines.enumerated()), id: \.offset) { i, l in
                        Text(l).font(.system(.caption, design: .monospaced)).textSelection(.enabled).id(i)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(8)
            }
            .background(.background.secondary, in: RoundedRectangle(cornerRadius: 6))
            .onChange(of: lines.count) { _, n in proxy.scrollTo(n - 1, anchor: .bottom) }
        }
    }
}
