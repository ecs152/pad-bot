import SwiftUI

struct RunPanel: View {
    @EnvironmentObject var bot: BotRunner
    @AppStorage("uncleared") private var uncleared = true
    @AppStorage("path") private var path = ""
    @AppStorage("runs") private var runs = 1
    @AppStorage("maxRuns") private var maxRuns = 20
    @AppStorage("extraStopWords") private var extraStopWords = ""
    @AppStorage("profile") private var profile = "profiles/lugner.toml"

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
                Picker("Team", selection: $profile) {
                    ForEach(teamFiles, id: \.self) { Text(($0 as NSString).lastPathComponent.replacingOccurrences(of: ".toml", with: "")).tag($0) }
                }
                Stepper("Runs: \(min(runs, maxRuns))", value: $runs, in: 1...max(1, maxRuns))
            }
            .disabled(bot.running)

            HStack {
                if bot.running {
                    Button(role: .destructive) { bot.stop() } label: { Label("Stop", systemImage: "stop.fill") }
                        .keyboardShortcut(".", modifiers: .command)
                } else {
                    Button { start() } label: { Label("Start", systemImage: "play.fill") }
                    .keyboardShortcut(.return, modifiers: .command)
                    .disabled(!uncleared && !path.contains("/"))
                }
                Spacer()
                Circle().fill(bot.running ? (bot.live ? Color.red : Color.orange) : Color.secondary)
                    .frame(width: 8, height: 8)
                Text(bot.status).font(.callout).lineLimit(2)
                if !bot.running && bot.status.localizedCaseInsensitiveContains("permission") {
                    Button("Fix permissions") { Permissions.shared.ensure() }
                }
            }
            .controlSize(.large)

            Text("Start taps and drags on the phone and takes your mouse. To stop, move the mouse to the top-left corner, or use Stop in the menu bar.")
                .font(.caption).foregroundStyle(.secondary)

            LogView(lines: bot.log)
        }
    }

    private var teamFiles: [String] {
        let names = (try? FileManager.default.contentsOfDirectory(atPath: ProfileStore.dir.path)) ?? []
        return Array(Set(names.filter { $0.hasSuffix(".toml") }.map { "profiles/" + $0 } + [profile])).sorted()
    }

    private func start() {
        var args = uncleared ? ["--uncleared"] : ["--path", path]
        args += ["--profile", profile]
        args += ["--runs", String(min(runs, maxRuns))]
        args.append("--live")  // no practice mode: a failed run only costs stamina
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
