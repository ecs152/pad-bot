import AppKit
import ApplicationServices
import SwiftUI

/// Screen Recording (to see the mirror window) and Accessibility (to tap). The bot runs as PAD Bot's child
/// process, so macOS checks PAD Bot's grants: asking here puts PAD Bot itself in the Settings lists.
final class Permissions: ObservableObject {
    static let shared = Permissions()
    @Published var screen = CGPreflightScreenCaptureAccess()
    @Published var accessibility = AXIsProcessTrusted()
    @Published var showSheet = false
    private var asked = false

    var allGranted: Bool { screen && accessibility }

    func refresh() {
        screen = CGPreflightScreenCaptureAccess()
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
            HStack {
                Button("Not now") { perms.showSheet = false }
                Spacer()
                Button("Quit and reopen") { relaunch() }
                Button("Check again") { perms.refresh() }.keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 460)
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            perms.refresh()
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
        let path = Bundle.main.bundlePath
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/sh")
        p.arguments = ["-c", "sleep 1; open \"$0\"", path]
        try? p.run()
        NSApp.terminate(nil)
    }
}
