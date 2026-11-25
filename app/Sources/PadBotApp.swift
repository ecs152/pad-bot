import AppKit
import SwiftUI

@main
struct PadBotApp: App {
    @StateObject private var bot = BotRunner()

    init() {
        // Defaults for Safety settings; @AppStorage reads these until the user changes them.
        UserDefaults.standard.register(defaults: ["maxRuns": 20, "alertOnStop": true, "extraStopWords": ""])
        if let i = CommandLine.arguments.firstIndex(of: "--snapshot"), i + 1 < CommandLine.arguments.count {
            Snapshot.renderAll(to: CommandLine.arguments[i + 1])
            exit(0)
        }
        // `open -n "PAD Bot.app" --args --permcheck FILE`: writes the grants macOS gives this build, then exits.
        // Run through `open` so macOS checks PAD Bot itself, not the terminal. app/build.sh uses it after installing.
        if let i = CommandLine.arguments.firstIndex(of: "--permcheck"), i + 1 < CommandLine.arguments.count {
            let p = Permissions.shared
            try? "screen=\(p.screen) accessibility=\(p.accessibility)\n".write(toFile: CommandLine.arguments[i + 1], atomically: true, encoding: .utf8)
            exit(0)
        }
        if let i = CommandLine.arguments.firstIndex(of: "--selftest"), i + 1 < CommandLine.arguments.count {
            SelfTest.run(replay: CommandLine.arguments[i + 1])
        }
    }

    var body: some Scene {
        WindowGroup("PAD Bot", id: "main") {
            MainView().environmentObject(bot).frame(minWidth: 520, minHeight: 600)
        }
        MenuBarExtra {
            MenuBarView().environmentObject(bot)
        } label: {
            Image(systemName: bot.running ? "play.circle.fill" : "square.grid.3x3")
        }
    }
}

struct MainView: View {
    @EnvironmentObject var bot: BotRunner
    @ObservedObject var perms = Permissions.shared

    var body: some View {
        TabView {
            ForEach(panels) { p in
                p.view(bot).tabItem { Label(p.title, systemImage: p.icon) }
            }
        }
        .padding()
        .sheet(isPresented: $perms.showSheet) { PermissionsSheet() }
        .onAppear { perms.ensure() }  // macOS prompts on first launch, not mid-run
    }
}
