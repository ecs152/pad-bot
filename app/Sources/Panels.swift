import SwiftUI

/// A tab in the main window. Each feature track adds one panel: write a SwiftUI view in its own file,
/// read what it needs from `BotRunner` (`events`, `lastTurn`, `running`, ...), and append one line below.
/// Bot data arrives as `@ev {json}` events; the contract is docs/events.md.
struct PanelSpec: Identifiable {
    let id: String
    let title: String
    let icon: String  // SF Symbol name
    let view: (BotRunner) -> AnyView
}

// Append new panels at the end so parallel branches merge cleanly.
let panels: [PanelSpec] = [
    PanelSpec(id: "run", title: "Run", icon: "play") { _ in AnyView(RunPanel()) },
    PanelSpec(id: "safety", title: "Safety", icon: "lock.shield") { _ in AnyView(SafetyPanel()) },
    PanelSpec(id: "teams", title: "Teams", icon: "person.3") { _ in AnyView(TeamsPanel()) },
]
