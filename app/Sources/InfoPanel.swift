import SwiftUI

/// Runs `padbot info` (read-only: screenshot + OCR + fan data, never taps) and keeps its last `info` event.
final class InfoLookup: ObservableObject {
    static let shared = InfoLookup()
    @Published var result: [String: Any] = [:]
    @Published var busy = false
    @Published var problem: String?

    func look(update: Bool = false) {
        guard !busy else { return }
        busy = true
        problem = nil
        let p = Process()
        p.executableURL = BotRunner.root.appendingPathComponent(".venv/bin/python")
        p.arguments = ["-u", "-m", "padbot", "info"] + (update ? ["--update"] : [])
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
                let ev = out.split(separator: "\n").last { $0.hasPrefix("@ev ") }
                if let ev { self.handle(String(ev)) } else { self.problem = out.split(separator: "\n").last.map(String.init) ?? "no output" }
            }
        }
    }

    /// Snapshot sample: Lügner plus the Beyond the Desert floor, as `padbot info` prints them.
    static let sample = ##"@ev {"type": "info", "updated": 1795077077, "monster": {"no": 13442, "name": "Lügner", "leader": {"name": "False Envoy of Peace", "text": "[No skyfall] 2.6x HP & RCV for Devil type; 150x ATK, reduce damage taken by 50%, and deal 15,000,000 additional true damage when activating [Cross Attack]"}, "active": {"name": "Blood Manipulation: Bluterei", "text": "Unlock all orbs; Create a cross of Dark orbs with its center at the 2nd row from the top and the 2nd column from the left; Enhance all Dark orbs; For 1 turn, bypass void damage shield effects; For 1 turn, bypass combo absorb shield effects", "turns": [7, 3]}, "awakenings": ["Resistance-Bind+", "Skill Boost+", "Resistance-Skill Bind", "Levitation", "Cross Attack+", "Cross Attack+", "Cross Attack+", "Part Break Bonus", "Skill Voice"], "keywords": ["Absorb", "Damage void", "Skyfall", "Lock", "Orb change", "Enhance orbs", "Reduce damage", "Combos", "True damage"]}, "dungeon": {"id": 214, "name": "Aither Desert", "floors": ["Hunter in the Desert", "Beyond the Desert", "Temple Under the Desert", "Guards of the Light", "Genie of the Lamp"], "floor": {"name": "Beyond the Desert", "stamina": 13, "battles": 3, "mult": [1, 1, 1], "reward": "", "enemies": [{"name": "Pyro Devil", "hp": 10866, "turns": 1}, {"name": "Harpie Devil", "hp": 11208, "turns": 1}, {"name": "Dub-topalit", "hp": 10, "turns": 3}, {"name": "Volt Chimera", "hp": 12800, "turns": 2}, {"name": "Fire Pengdra", "hp": 16320, "turns": 2}, {"name": "Ruby Pengdra", "hp": 5790, "turns": 2}, {"name": "Genie", "hp": 136308, "turns": 1}]}}}"##

    func handle(_ line: String) {
        guard let obj = try? JSONSerialization.jsonObject(with: Data(line.dropFirst(4).utf8)) as? [String: Any] else { return }
        if let e = obj["error"] as? String { problem = e } else { result = obj }
    }
}

struct InfoPanel: View {
    @ObservedObject var info = InfoLookup.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Button { info.look() } label: { Label("Look at screen", systemImage: "text.viewfinder") }
                    .keyboardShortcut("l")
                Button("Update fan data") { info.look(update: true) }
                if info.busy { ProgressView().controlSize(.small) }
                Spacer()
                if let t = info.result["updated"] as? Double {
                    Text("Data \(Date(timeIntervalSince1970: t).formatted(date: .abbreviated, time: .omitted))")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            if let p = info.problem { Text(p).font(.caption).foregroundStyle(.red) }
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if let m = info.result["monster"] as? [String: Any] { monster(m) }
                    if let d = info.result["dungeon"] as? [String: Any] { dungeon(d) }
                    if !info.result.isEmpty && info.result["monster"] is NSNull && info.result["dungeon"] is NSNull {
                        Text("No monster or dungeon name recognised on this screen.").foregroundStyle(.secondary)
                    }
                    if info.result.isEmpty && info.problem == nil {
                        Text("Open a monster, a helper or a floor list in the game, then Look at screen. Reads the screen only; it never taps.")
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
            }
            Text("Fan data: DadGuide (NA). Kept in data/, not in git.").font(.caption2).foregroundStyle(.tertiary)
        }
    }

    func monster(_ m: [String: Any]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("\(m["name"] as? String ?? "?")  No.\(String(m["no"] as? Int ?? 0))").font(.title3.bold())
            chips(m["keywords"] as? [String] ?? [])
            if let l = m["leader"] as? [String: Any] { skill("Leader", l["name"], l["text"], nil) }
            if let a = m["active"] as? [String: Any] {
                let t = a["turns"] as? [Int] ?? []
                skill("Active", a["name"], a["text"], t.count == 2 ? "\(t[0]) → \(t[1]) turns" : nil)
            }
            if let aw = m["awakenings"] as? [String], !aw.isEmpty {
                Text("Awakenings: " + aw.joined(separator: ", ")).font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    func skill(_ kind: String, _ name: Any?, _ text: Any?, _ turns: String?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text("\(kind): \(name as? String ?? "")").font(.headline)
                if let turns { Text(turns).font(.caption).foregroundStyle(.secondary) }
            }
            Text(text as? String ?? "").font(.callout)
        }
    }

    func chips(_ words: [String]) -> some View {
        Text(words.joined(separator: " · ")).font(.callout.weight(.medium)).foregroundStyle(Color.accentColor)
    }

    func dungeon(_ d: [String: Any]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(d["name"] as? String ?? "?").font(.title3.bold())
            if let f = d["floor"] as? [String: Any] {
                let mult = f["mult"] as? [Double] ?? []
                Text(f["name"] as? String ?? "").font(.headline)
                Text("\(f["stamina"] as? Int ?? 0) stamina · \(f["battles"] as? Int ?? 0) battles"
                     + (mult.count == 3 && mult != [1, 1, 1] ? " · HP ×\(fmt(mult[0])) ATK ×\(fmt(mult[1])) DEF ×\(fmt(mult[2]))" : ""))
                    .font(.callout)
                if let r = f["reward"] as? String, !r.isEmpty { Text("Reward: \(r)").font(.callout) }
                Text("Enemies").font(.subheadline.bold()).padding(.top, 4)
                ForEach(Array((f["enemies"] as? [[String: Any]] ?? []).enumerated()), id: \.offset) { _, e in
                    HStack {
                        Text(e["name"] as? String ?? "?")
                        Spacer()
                        Text("HP \((e["hp"] as? Int ?? 0).formatted()) · attacks every \(e["turns"] as? Int ?? 0) turn(s)")
                            .foregroundStyle(.secondary)
                    }.font(.callout)
                }
            } else if let floors = d["floors"] as? [String] {
                Text("Floors: " + floors.joined(separator: ", ")).font(.callout)
            }
        }
    }

    func fmt(_ x: Double) -> String { x == x.rounded() ? String(Int(x)) : String(x) }
}
