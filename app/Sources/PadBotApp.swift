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

    var body: some View {
        TabView {
            ForEach(panels) { p in
                p.view(bot).tabItem { Label(p.title, systemImage: p.icon) }
            }
        }
        .padding()
    }
}
