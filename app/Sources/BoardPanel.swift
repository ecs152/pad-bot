import SwiftUI

/// The bot's read of the 30 orbs and the drag it planned, from the latest `turn` event.
/// Same drawing as padbot/boardview.py (used by `padbot watch`).
struct BoardPanel: View {
    @EnvironmentObject var bot: BotRunner

    static let colours: [Character: Color] = [
        "R": Color(red: 0.90, green: 0.24, blue: 0.24), "B": Color(red: 0.16, green: 0.55, blue: 0.90),
        "G": Color(red: 0.27, green: 0.75, blue: 0.27), "L": Color(red: 0.94, green: 0.86, blue: 0.24),
        "D": Color(red: 0.59, green: 0.24, blue: 0.67), "H": Color(red: 0.96, green: 0.47, blue: 0.75),
        "J": .gray, "P": Color(red: 0.35, green: 0.20, blue: 0.47), "M": Color(red: 0.20, green: 0.08, blue: 0.24),
    ]
    static let names: [String: String] = ["R": "fire", "B": "water", "G": "wood", "L": "light", "D": "dark", "H": "heal"]

    var body: some View {
        let d = bot.lastTurn?.data ?? [:]
        let board = d["board"] as? [String] ?? []
        let route = d["route"] as? [[Int]] ?? []
        VStack(alignment: .leading, spacing: 8) {
            if board.count == 5 {
                let steps = max(route.count - 1, 0)
                Text("Turn \(d["turn"] as? Int ?? 0) · \(steps) step\(steps == 1 ? "" : "s")").font(.headline)
                Text("Goal: \(Self.goalText(d["goal"] as? [String: Any] ?? [:]))")
                let mech = d["mechanics"] as? [String] ?? []
                Text("Enemy icons: \(mech.isEmpty ? "none" : mech.joined(separator: ", "))").foregroundStyle(.secondary)
                BoardView(board: board, route: route).aspectRatio(6.0 / 5.0, contentMode: .fit)
            } else {
                Text("Waiting for the bot's first turn…").foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    /// {"crosses": {"D": 1}, "min_combos": 3} -> "dark cross x1, 3+ combos"
    static func goalText(_ g: [String: Any]) -> String {
        let n = { (k: String) in names[k] ?? k }
        var parts = (g["crosses"] as? [String: Int] ?? [:]).sorted { $0.key < $1.key }.map { "\(n($0.key)) cross x\($0.value)" }
        parts += (g["link"] as? [String: Int] ?? [:]).sorted { $0.key < $1.key }.map { "\($0.value)+ \(n($0.key)) linked" }
        if let c = g["min_combos"] as? Int, c > 0 { parts.append("\(c)+ combos") }
        if let a = g["avoid"] as? [String], !a.isEmpty { parts.append("avoid " + a.map(n).joined(separator: ", ")) }
        return parts.isEmpty ? "any match" : parts.joined(separator: ", ")
    }
}

struct BoardView: View {
    let board: [String]
    let route: [[Int]]

    var body: some View {
        Canvas { ctx, size in
            let cell = min(size.width / 6, size.height / 5)
            let centre = { (r: Int, c: Int) in CGPoint(x: (CGFloat(c) + 0.5) * cell, y: (CGFloat(r) + 0.5) * cell) }
            for (r, row) in board.prefix(5).enumerated() {
                for (c, k) in row.prefix(6).enumerated() {
                    let p = centre(r, c)
                    ctx.fill(Path(CGRect(x: p.x - cell / 2, y: p.y - cell / 2, width: cell, height: cell)),
                             with: .color(.gray.opacity((r + c) % 2 == 0 ? 0.12 : 0.2)))
                    let rad = cell * 0.4
                    ctx.fill(Path(ellipseIn: CGRect(x: p.x - rad, y: p.y - rad, width: 2 * rad, height: 2 * rad)),
                             with: .color(BoardPanel.colours[k] ?? .gray.opacity(0.5)))
                    ctx.draw(Text(k == "." ? "?" : String(k)).font(.system(size: cell * 0.28, weight: .bold)).foregroundColor(.white), at: p)
                }
            }
            let pts = route.filter { $0.count == 2 }.map { centre($0[0], $0[1]) }
            guard pts.count >= 2 else { return }
            var line = Path()
            line.addLines(pts)
            ctx.stroke(line, with: .color(.black.opacity(0.8)), style: StrokeStyle(lineWidth: cell * 0.14, lineCap: .round, lineJoin: .round))
            ctx.stroke(line, with: .color(.white), style: StrokeStyle(lineWidth: cell * 0.08, lineCap: .round, lineJoin: .round))
            for (i, p) in pts.enumerated().dropFirst().dropLast() {
                ctx.draw(Text("\(i)").font(.system(size: cell * 0.2, weight: .semibold)).foregroundColor(.white),
                         at: CGPoint(x: p.x + cell * 0.18, y: p.y - cell * 0.18))
            }
            for (p, colour) in [(pts[0], Color.green), (pts[pts.count - 1], Color.red)] {
                let rr = cell * 0.14
                let dot = Path(ellipseIn: CGRect(x: p.x - rr, y: p.y - rr, width: 2 * rr, height: 2 * rr))
                ctx.fill(dot, with: .color(colour))
                ctx.stroke(dot, with: .color(.white), lineWidth: 2)
            }
        }
        .accessibilityLabel("Board with planned drag of \(max(route.count - 1, 0)) steps")
    }
}
