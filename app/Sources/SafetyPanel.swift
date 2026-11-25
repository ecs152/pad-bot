import SwiftUI

struct SafetyPanel: View {
    @AppStorage("maxRuns") private var maxRuns = 20
    @AppStorage("alertOnStop") private var alertOnStop = true
    @AppStorage("extraStopWords") private var extraStopWords = ""

    var body: some View {
        Form {
            Section {
                Toggle("Never spend Magic Stones", isOn: .constant(true)).disabled(true)
                Text("Always on. The bot stops on Continue, Magic Stone, Purchase, Revive and stamina prompts, and never taps them. This can't be turned off here.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("Extra stop words") {
                TextField("Comma-separated", text: $extraStopWords, prompt: Text("e.g. Rank Up, Event"))
                Text("The bot also stops when any of these appears on screen.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section {
                Stepper("Max runs per start: \(maxRuns)", value: $maxRuns, in: 1...200)
                Toggle("Alert me when it stops or needs me", isOn: $alertOnStop)
                Text("Plays a sound and bounces the Dock icon. A Mac notification is always sent.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
    }
}
