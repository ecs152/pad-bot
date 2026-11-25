import SwiftUI

// Team profiles (profiles/*.toml). TOML is read and written by `python -m padbot.profile show|save`,
// which also validates, so the app and the bot agree on what a profile means.

struct Goal: Codable, Equatable {
    var crosses: [String: Int]?
    var link: [String: Int]?
    var min_combos: Int?
    var avoid: [String]?
}

struct Rule: Codable, Equatable {
    var skills: [Int]?
    var first_of: [Int]?
    var goal: Goal?
}

struct Defaults: Codable, Equatable {
    var first_of: [Int]?
    var skills: [Int]?
    var goal: Goal?
    var fallback_goal: Goal?
}

struct Profile: Codable, Equatable {
    var name = ""
    var notes: String?
    var max_steps: Int?
    var leader_skill: String?
    var slots: [String: String]?
    var `default`: Defaults?
    var cooldowns: [String: Int]?
    var on: [String: Rule]?
}

let orbs: [(key: String, name: String, color: Color)] = [
    ("R", "Fire", .red), ("B", "Water", .blue), ("G", "Wood", .green),
    ("L", "Light", .yellow), ("D", "Dark", .purple), ("H", "Heart", .pink),
]

/// Loads and saves one profile through the bot's Python.
final class ProfileStore: ObservableObject {
    @Published var profile = Profile()
    @Published var saved = Profile()
    @Published var errors: [String] = []
    @Published var files: [String] = []
    var dirty: Bool { profile != saved }

    static var dir: URL { BotRunner.root.appendingPathComponent("profiles") }

    func refreshFiles() {
        let names = (try? FileManager.default.contentsOfDirectory(atPath: Self.dir.path)) ?? []
        files = names.filter { $0.hasSuffix(".toml") }.sorted().map { "profiles/" + $0 }
    }

    func load(_ path: String) {
        struct Shown: Decodable { var profile: Profile?; var errors: [String] }
        let out = Self.python(["show", path])
        guard let s = try? JSONDecoder().decode(Shown.self, from: out) else {
            errors = ["Couldn't read \(path): \(String(decoding: out, as: UTF8.self))"]
            return
        }
        (profile, saved, errors) = (s.profile ?? Profile(), s.profile ?? Profile(), s.errors)
    }

    @discardableResult
    func save(_ path: String, _ p: Profile? = nil) -> Bool {
        struct Saved: Decodable { var errors: [String] }
        let enc = JSONEncoder()
        enc.outputFormatting = .sortedKeys  // stable [on.*] order in the file
        let out = Self.python(["save", path], input: try? enc.encode(p ?? profile))
        errors = (try? JSONDecoder().decode(Saved.self, from: out))?.errors
            ?? ["Couldn't save: \(String(decoding: out, as: UTF8.self))"]
        if errors.isEmpty && p == nil { saved = profile }
        return errors.isEmpty
    }

    static func python(_ args: [String], input: Data? = nil) -> Data {
        let p = Process()
        p.executableURL = BotRunner.root.appendingPathComponent(".venv/bin/python")
        p.arguments = ["-m", "padbot.profile"] + args
        p.currentDirectoryURL = BotRunner.root
        let (inp, out) = (Pipe(), Pipe())
        (p.standardInput, p.standardOutput, p.standardError) = (inp, out, out)
        do { try p.run() } catch { return Data(#"{"errors":["couldn't start Python: \#(error.localizedDescription)"]}"#.utf8) }
        if let input { inp.fileHandleForWriting.write(input) }
        try? inp.fileHandleForWriting.close()
        let data = out.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        return data
    }
}

struct TeamsPanel: View {
    @AppStorage("profile") private var path = "profiles/lugner.toml"
    @StateObject private var store = ProfileStore()
    @State private var newName = ""
    @State private var askNew = false
    @State private var newAbility = ""

    var body: some View {
        VStack(spacing: 10) {
            HStack {
                Picker("Team", selection: $path) {
                    ForEach(store.files, id: \.self) { Text(fileLabel($0)).tag($0) }
                }
                .disabled(store.dirty)
                .help(store.dirty ? "Save or revert first" : "The team the bot uses on the next run")
                Button("New team…") { newName = ""; askNew = true }.disabled(store.dirty)
            }
            form
            if !store.errors.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(store.errors, id: \.self) { Label($0, systemImage: "exclamationmark.triangle.fill") }
                }
                .font(.callout).foregroundStyle(.red).frame(maxWidth: .infinity, alignment: .leading)
            }
            HStack {
                Text(store.dirty ? "Unsaved changes" : "Saved to \(path)").font(.callout).foregroundStyle(.secondary)
                Spacer()
                Button("Revert") { store.load(path) }.disabled(!store.dirty)
                Button("Save") { store.save(path) }.keyboardShortcut("s").disabled(!store.dirty)
            }
        }
        .onAppear { store.refreshFiles(); store.load(path) }
        .onChange(of: path) { _, p in store.load(p) }
        .alert("New team", isPresented: $askNew) {
            TextField("Name", text: $newName)
            Button("Create") { createTeam() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Starts from the current team's rules. Edit them, then Save.")
        }
    }

    private var form: some View {
        Form {
            Section {
                TextField("Name", text: $store.profile.name)
                TextField("Notes", text: opt($store.profile.notes, ""), axis: .vertical).lineLimit(1...3)
                TextField("Leader skill name", text: opt($store.profile.leader_skill, ""),
                          prompt: Text("Finds this team on the Enter screen"))
                Stepper("Longest drag: \(store.profile.max_steps ?? 12) steps",
                        value: opt($store.profile.max_steps, 12), in: 1...30)
            }
            Section {
                ForEach(1...6, id: \.self) { slotRow($0) }
            } header: {
                Text("Team")
            } footer: {
                Text("Cooldown is turns between uses: the bot only taps a portrait once it's up.").foregroundStyle(.secondary)
            }
            Section {
                SlotPicker(title: "Fire order", order: true, slots: defaults.first_of, names: store.profile.slots)
                SlotPicker(title: "Also fire every turn", order: false, slots: defaults.skills, names: store.profile.slots)
            } header: {
                Text("Each turn")
            } footer: {
                Text("Fires the first skill in the order that is off cooldown, then stops.").foregroundStyle(.secondary)
            }
            Section("Board goal") { GoalEditor(goal: opt(defaults.goal, Goal())) }
            Section {
                GoalEditor(goal: opt(defaults.fallback_goal, Goal(min_combos: 1)))
            } header: {
                Text("Stall")
            } footer: {
                Text("Used when a needed counter isn't charged yet (the turn's skill is skipped so skills charge), or the board goal is out of reach.").foregroundStyle(.secondary)
            }
            Section {
                ForEach(abilities, id: \.self) { counterRow($0) }
                HStack {
                    TextField("Enemy ability", text: $newAbility, prompt: Text("e.g. awoken_bind"))
                    Button("Add") {
                        store.profile.on = (store.profile.on ?? [:]).merging([abilityKey: Rule()]) { a, _ in a }
                        newAbility = ""
                    }.disabled(abilityKey.isEmpty)
                }
            } header: {
                Text("Counters")
            } footer: {
                Text("When the ability's icon is seen, these skills fire first. If none is charged, the bot stalls.").foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
    }

    private func slotRow(_ s: Int) -> some View {
        let k = String(s)
        return LabeledContent {
            HStack {
                TextField("Slot \(s)", text: Binding(
                    get: { store.profile.slots?[k] ?? "" },
                    set: { store.profile.slots = (store.profile.slots ?? [:]).merging([k: $0]) { $1 }.filter { !$0.value.isEmpty } }),
                    prompt: Text("Monster"))
                    .labelsHidden().textFieldStyle(.roundedBorder).frame(width: 230)
                Stepper(value: Binding(
                    get: { store.profile.cooldowns?[k] ?? 0 },
                    set: { store.profile.cooldowns = (store.profile.cooldowns ?? [:]).merging([k: $0]) { $1 }.filter { $0.value > 0 } }),
                    in: 0...99) {
                    let cd = store.profile.cooldowns?[k] ?? 0
                    Text(cd == 0 ? "no cooldown" : "cooldown \(cd)").monospacedDigit().frame(width: 92, alignment: .trailing)
                }
                .fixedSize()
            }
        } label: {
            Text("\(s)").monospacedDigit().foregroundStyle(.secondary)
        }
    }

    private func counterRow(_ a: String) -> some View {
        let rule = Binding(get: { store.profile.on?[a] ?? Rule() }, set: { store.profile.on?[a] = $0 })
        return VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(a.replacingOccurrences(of: "_", with: " ").capitalized).bold()
                if rule.wrappedValue.goal != nil || rule.wrappedValue.first_of != nil {
                    Text("+ own goal/order (edit in file)").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button(role: .destructive) { store.profile.on?[a] = nil } label: { Image(systemName: "trash") }
                    .buttonStyle(.borderless).help("Remove")
            }
            SlotPicker(title: "Countered by", order: false, slots: opt(rule.skills, []), names: store.profile.slots,
                       empty: "nothing (the turn's skill covers it)")
        }
    }

    private var defaults: Binding<Defaults> { opt($store.profile.default, Defaults()) }
    private var abilities: [String] { (store.profile.on ?? [:]).keys.sorted() }
    private var abilityKey: String {
        newAbility.lowercased().split(whereSeparator: { !$0.isLetter && !$0.isNumber }).joined(separator: "_")
    }

    private func fileLabel(_ f: String) -> String {
        f == path && !store.profile.name.isEmpty ? store.saved.name : (f as NSString).lastPathComponent.replacingOccurrences(of: ".toml", with: "")
    }

    private func createTeam() {
        let slug = newName.lowercased().split(whereSeparator: { !$0.isLetter && !$0.isNumber }).joined(separator: "-")
        let f = "profiles/\(slug.isEmpty ? "team" : slug).toml"
        guard !FileManager.default.fileExists(atPath: BotRunner.root.appendingPathComponent(f).path) else {
            store.errors = ["\(f) already exists"]
            return
        }
        var p = store.saved
        p.name = newName.isEmpty ? "New team" : newName
        p.notes = nil
        if store.save(f, p) { store.refreshFiles(); path = f }
    }
}

/// Picks slots 1-6. With `order`, taps append to the end and the position shows on the chip.
struct SlotPicker: View {
    let title: String
    let order: Bool
    @Binding var slots: [Int]
    var names: [String: String]?
    var empty = "none"

    init(title: String, order: Bool, slots: Binding<[Int]?>, names: [String: String]?, empty: String = "none") {
        self.init(title: title, order: order, slots: opt(slots, []), names: names, empty: empty)
    }

    init(title: String, order: Bool, slots: Binding<[Int]>, names: [String: String]?, empty: String = "none") {
        (self.title, self.order, self._slots, self.names, self.empty) = (title, order, slots, names, empty)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
                Text(title)
                Spacer()
                ForEach(1...6, id: \.self) { s in
                    let i = slots.firstIndex(of: s)
                    Button {
                        if let i { slots.remove(at: i) } else { slots.append(s) }
                    } label: {
                        Text(i.map { order ? "\(s)·\($0 + 1)" : "\(s)" } ?? "\(s)")
                            .monospacedDigit().frame(minWidth: order ? 30 : 18).padding(.vertical, 3).padding(.horizontal, 5)
                            .foregroundStyle(i == nil ? Color.primary : .white)
                            .background(i == nil ? Color.secondary.opacity(0.2) : .accentColor, in: RoundedRectangle(cornerRadius: 5))
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(i == nil ? [] : .isSelected)
                    .help(names?[String(s)] ?? "Slot \(s)")
                }
            }
            Text(summary).font(.caption).foregroundStyle(.secondary)
        }
    }

    private var summary: String {
        if slots.isEmpty { return empty.prefix(1).uppercased() + empty.dropFirst() }
        func label(_ s: Int) -> String {
            // "Lügner (leader)" -> "1 Lügner": the bracketed note is too long for a summary line
            guard let n = names?[String(s)] else { return "slot \(s)" }
            return "\(s) " + (n.components(separatedBy: " (").first ?? n)
        }
        return slots.map(label).joined(separator: order ? " → " : ", ")
    }
}

/// crosses / link / min_combos / avoid, matching padbot/solver.py.
struct GoalEditor: View {
    @Binding var goal: Goal

    var body: some View {
        countRows("cross", \.crosses, start: 1, range: 1...3)
        countRows("linked", \.link, start: 5, range: 3...30)
        Stepper("At least \(goal.min_combos ?? 0) combo(s)", value: opt($goal.min_combos, 0), in: 0...10)
        HStack(spacing: 6) {
            Text("Avoid matching")
            Spacer()
            ForEach(orbs, id: \.key) { o in
                let on = goal.avoid?.contains(o.key) ?? false
                Button { toggleAvoid(o.key) } label: { OrbDot(color: o.color, on: on) }
                    .buttonStyle(.plain).help(o.name)
            }
        }
        HStack {
            Text(summary).font(.caption).foregroundStyle(.secondary)
            Spacer()
            Menu("Add") {
                ForEach(orbs, id: \.key) { o in
                    Button("\(o.name) cross") { goal.crosses = (goal.crosses ?? [:]).merging([o.key: 1]) { a, _ in a } }
                }
                Divider()
                ForEach(orbs, id: \.key) { o in
                    Button("\(o.name) linked orbs") { goal.link = (goal.link ?? [:]).merging([o.key: 5]) { a, _ in a } }
                }
            }
            .fixedSize()
        }
    }

    @ViewBuilder
    private func countRows(_ label: String, _ kp: WritableKeyPath<Goal, [String: Int]?>, start: Int, range: ClosedRange<Int>) -> some View {
        ForEach(orbs.filter { goal[keyPath: kp]?[$0.key] != nil }, id: \.key) { o in
            let n = Binding(get: { goal[keyPath: kp]?[o.key] ?? start }, set: { goal[keyPath: kp]?[o.key] = $0 })
            HStack {
                OrbDot(color: o.color, on: true)
                Stepper(label == "cross" ? "\(n.wrappedValue) \(o.name.lowercased()) cross(es)" : "\(n.wrappedValue) \(o.name.lowercased()) orbs linked",
                        value: n, in: range)
                Button(role: .destructive) {
                    goal[keyPath: kp]?[o.key] = nil
                    if goal[keyPath: kp]?.isEmpty == true { goal[keyPath: kp] = nil }
                } label: { Image(systemName: "minus.circle") }.buttonStyle(.borderless)
            }
        }
    }

    private func toggleAvoid(_ k: String) {
        var a = goal.avoid ?? []
        if let i = a.firstIndex(of: k) { a.remove(at: i) } else { a.append(k) }
        goal.avoid = a.isEmpty ? nil : a.sorted()
    }

    private var summary: String {
        var parts: [String] = []
        for o in orbs {
            if let n = goal.crosses?[o.key] { parts.append("\(n) \(o.name.lowercased()) cross") }
            if let n = goal.link?[o.key] { parts.append("link \(n) \(o.name.lowercased())") }
        }
        if let n = goal.min_combos, n > 0 { parts.append("\(n)+ combos") }
        return parts.isEmpty ? "Any route" : "Shortest drag that makes " + parts.joined(separator: ", ")
    }
}

struct OrbDot: View {
    let color: Color
    let on: Bool
    var body: some View {
        Circle().fill(on ? color : color.opacity(0.18)).frame(width: 16, height: 16)
            .overlay(Circle().stroke(color, lineWidth: on ? 0 : 1))
    }
}

/// A binding to an optional that reads as `fallback` when nil.
func opt<T>(_ b: Binding<T?>, _ fallback: T) -> Binding<T> {
    Binding(get: { b.wrappedValue ?? fallback }, set: { b.wrappedValue = $0 })
}
