import SwiftUI

/// Runs `padbot coverage` (fan data only, never touches the phone): which enemy mechanics a dungeon uses,
/// and which of them the team picked on the Run tab counters, with which slot.
final class CoverageCheck: ObservableObject {
    static let shared = CoverageCheck()
    @Published var result: [String: Any] = [:]
    @Published var busy = false
    @Published var problem: String?

    func check(profile: String, dungeon: String, floor: String) {
        guard !busy else { return }
        (busy, problem) = (true, nil)
        var args = ["-u", "-m", "padbot", "coverage", "--profile", profile]
        if !dungeon.isEmpty { args += ["--dungeon", dungeon] }
        if !floor.isEmpty { args += ["--floor", floor] }
        let p = Process()
        p.executableURL = BotRunner.root.appendingPathComponent(".venv/bin/python")
        p.arguments = args
        p.currentDirectoryURL = BotRunner.root
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        DispatchQueue.global().async {
            var out = ""
            do {
                try p.run()
                out = String(decoding: pipe.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
                p.waitUntilExit()
            } catch { out = "couldn't start python (\(error.localizedDescription))" }
            DispatchQueue.main.async {
                self.busy = false
                if let ev = out.split(separator: "\n").last(where: { $0.hasPrefix("@ev ") }) {
                    self.handle(String(ev))
                } else {
                    self.problem = out.split(separator: "\n").last.map(String.init) ?? "no output"
                }
            }
        }
    }

    func handle(_ line: String) {
        guard let obj = try? JSONSerialization.jsonObject(with: Data(line.dropFirst(4).utf8)) as? [String: Any] else { return }
        result = obj
        problem = obj["error"] as? String
    }

    /// Snapshot sample: the Lügner team against a hard challenge dungeon (shortened).
    static let sample = ##"@ev {"type": "coverage", "dungeon": "Weekend Challenge!", "unknown": ["4: Gunsword (Eruption Slash)", "5: Absorb voider"], "rules": {"damage_void": [1, 2, 6], "combo_absorb": [1, 2, 6]}, "rows": [{"key": "damage_absorb", "label": "Damage absorb", "status": "gap", "preempt": true, "how": "A damage-absorb void active, or hit for less than the threshold.", "by": []}, {"key": "awoken_bind", "label": "Awoken bind", "status": "gap", "preempt": true, "how": "Clear it with an active; nothing resists it.", "by": []}, {"key": "bind", "label": "Bind", "status": "partial", "preempt": true, "how": "", "by": [{"slot": 1, "detail": "Resistance-Bind+ x1"}, {"slot": 3, "detail": "Resistance-Bind+ x1"}]}, {"key": "roulette", "label": "Roulette / spinners", "status": "manage", "preempt": false, "how": "Avoid or change those orbs.", "by": []}, {"key": "combo_absorb", "label": "Combo absorb", "status": "full", "preempt": true, "how": "", "by": [{"slot": 1, "detail": "bypass combo absorb"}, {"slot": 2, "detail": "bypass combo absorb"}]}, {"key": "damage_void", "label": "Damage void", "status": "full", "preempt": true, "how": "", "by": [{"slot": 1, "detail": "bypass void damage"}]}]}"##
}

struct CoveragePanel: View {
    @ObservedObject var cov = CoverageCheck.shared
    @AppStorage("profile") private var profile = "profiles/lugner.toml"  // team picked on the Run tab
    @AppStorage("coverageDungeon") private var dungeon = ""
    @AppStorage("coverageFloor") private var floor = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                TextField("Dungeon", text: $dungeon, prompt: Text("Dungeon name"))
                TextField("Floor", text: $floor, prompt: Text("Floor (optional)")).frame(maxWidth: 160)
                Button { cov.check(profile: profile, dungeon: dungeon, floor: floor) } label: {
                    Label("Check", systemImage: "checklist")
                }
                .disabled(cov.busy)
                if cov.busy { ProgressView().controlSize(.small) }
            }
            Text("Team: \(URL(fileURLWithPath: profile).deletingPathExtension().lastPathComponent) (pick it on the Run tab)")
                .font(.caption).foregroundStyle(.secondary)
            if let p = cov.problem { Label(p, systemImage: "exclamationmark.triangle").foregroundStyle(.orange) }
            if let unknown = cov.result["unknown"] as? [String], !unknown.isEmpty {
                Label("Not found in fan data, so not counted: \(unknown.joined(separator: "; ")). Use the card's exact name on the Teams tab.",
                      systemImage: "questionmark.circle").font(.callout).foregroundStyle(.secondary)
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(Array(rows.enumerated()), id: \.offset) { _, r in row(r) }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            Spacer(minLength: 0)
            Text("Gaps first. Full = an active (or enough resists) covers it. Manage = no skill counters it; play around it.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    private var rows: [[String: Any]] { cov.result["rows"] as? [[String: Any]] ?? [] }

    @ViewBuilder private func row(_ r: [String: Any]) -> some View {
        let status = r["status"] as? String ?? ""
        let (icon, colour): (String, Color) = switch status {
        case "gap": ("xmark.octagon.fill", .red)
        case "partial": ("exclamationmark.circle.fill", .orange)
        case "full": ("checkmark.circle.fill", .green)
        default: ("info.circle", .secondary)
        }
        let by = (r["by"] as? [[String: Any]] ?? []).map { "slot \($0["slot"] ?? "?") \($0["detail"] ?? "")" }
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Image(systemName: icon).foregroundStyle(colour)
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(r["label"] as? String ?? "").bold()
                    if r["preempt"] as? Bool == true {
                        Text("pre-emptive").font(.caption2).padding(.horizontal, 5)
                            .background(.orange.opacity(0.2), in: Capsule())
                    }
                }
                Text(by.isEmpty ? (r["how"] as? String ?? "") : by.joined(separator: ", "))
                    .font(.callout).foregroundStyle(.secondary)
            }
        }
    }
}
