import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject var bot: BotRunner
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Text(bot.status)
        Divider()
        if bot.running {
            Button("Stop") { bot.stop() }.keyboardShortcut(".")
        }
        Button("Open PAD Bot") {
            openWindow(id: "main")
            NSApp.activate(ignoringOtherApps: true)
        }
        Button("Quit") {
            bot.stop()
            NSApp.terminate(nil)
        }
        .keyboardShortcut("q")
    }
}
