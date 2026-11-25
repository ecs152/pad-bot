import AppKit
import ApplicationServices
import SwiftUI

/// Screen Recording (to see the mirror window) and Accessibility (to tap). The bot runs as PAD Bot's child
/// process, so macOS checks PAD Bot's grants: asking here puts PAD Bot itself in the Settings lists.
final class Permissions: ObservableObject {
    static let shared = Permissions()
    @Published var screen = Permissions.screenGranted()
    @Published var accessibility = AXIsProcessTrusted()
    @Published var showSheet = false
    private var asked = false

    var allGranted: Bool { screen && accessibility }

    @Published var checked = false  // a Check again found something still off: say so instead of doing nothing

    /// CGPreflightScreenCaptureAccess keeps its first answer until the app restarts, so a grant made while the
    /// app is open goes unseen. Window titles of other apps are only visible with the grant: read them instead.
    static func screenGranted() -> Bool {
        if CGPreflightScreenCaptureAccess() { return true }
        let me = getpid()
        let infos = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
        return infos.contains { w in
            // normal app windows only (layer 0): system ones such as the menu bar can show titles regardless
            (w[kCGWindowOwnerPID as String] as? Int32) != me && (w[kCGWindowLayer as String] as? Int) == 0
                && !["Dock", "Window Server"].contains(w[kCGWindowOwnerName as String] as? String ?? "")
                && !((w[kCGWindowName as String] as? String) ?? "").isEmpty
        }
    }

    func refresh() {
        screen = Permissions.screenGranted()
        accessibility = AXIsProcessTrusted()
        if allGranted { showSheet = false }
    }

    /// Shows macOS's own prompts once per launch, then the sheet. Returns true if nothing is missing.
    @discardableResult func ensure() -> Bool {
        refresh()
        if allGranted { return true }
        if !asked {
            asked = true
            if !screen { CGRequestScreenCaptureAccess() }
            if !accessibility {
                let opt = kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String
                AXIsProcessTrustedWithOptions([opt: true] as CFDictionary)
            }
        }
        showSheet = true
        return false
    }

    static func open(_ pane: String) {
        NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security?\(pane)")!)
    }
}

struct PermissionsSheet: View {
    @ObservedObject var perms = Permissions.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("PAD Bot needs two permissions").font(.title3).bold()
            row("Screen Recording", "To see the iPhone Mirroring window.", perms.screen, "Privacy_ScreenCapture")
            row("Accessibility", "To tap and drag on the phone.", perms.accessibility, "Privacy_Accessibility")
            Text("Turn PAD Bot on in each list. macOS may ask you to quit and reopen PAD Bot after Screen Recording.")
                .font(.callout).foregroundStyle(.secondary)
            if perms.checked && !perms.allGranted {
                Text("Still off. Turn PAD Bot on in the list, or click Quit and reopen if you already did.")
                    .font(.callout).foregroundStyle(.orange)
            }
            HStack {
                Button("Not now") { perms.showSheet = false }
                Spacer()
                Button("Quit and reopen") { relaunch() }
                Button("Check again") { perms.refresh(); perms.checked = true }.keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 460)
        .onReceive(Timer.publish(every: 1, on: .main, in: .common).autoconnect()) { _ in
            perms.refresh()  // closes the sheet by itself once both are on
        }
    }

    private func row(_ name: String, _ why: String, _ ok: Bool, _ pane: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Image(systemName: ok ? "checkmark.circle.fill" : "xmark.circle.fill").foregroundStyle(ok ? .green : .red)
            VStack(alignment: .leading) {
                Text(name).bold()
                Text(why).font(.callout).foregroundStyle(.secondary)
            }
            Spacer()
            if !ok { Button("Open Settings") { Permissions.open(pane) } }
        }
    }

    private func relaunch() {
        // A second copy starts first, then this one quits: a helper process could die with the app.
        let cfg = NSWorkspace.OpenConfiguration()
        cfg.createsNewApplicationInstance = true
        NSWorkspace.shared.openApplication(at: Bundle.main.bundleURL, configuration: cfg) { _, _ in
            DispatchQueue.main.async { exit(0) }  // exit, not terminate: a sheet can make terminate a no-op
        }
    }
}
