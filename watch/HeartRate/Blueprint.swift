import SwiftUI

/// Fitness Friday's palette, so the wrist matches the page it drives
/// (`overlays/fitness-friday/blueprint.css`, ADR 0027).
extension Color {
    static let royal = Color(red: 0.110, green: 0.255, blue: 0.831)      // #1c41d4
    static let royalDeep = Color(red: 0.059, green: 0.149, blue: 0.565)  // #0f2690
    static let ink = Color(red: 1.000, green: 0.839, blue: 0.039)        // #ffd60a
    static let paper = Color(red: 0.957, green: 0.969, blue: 1.000)      // #f4f7ff
}

/// The drafting sheet: the royal gradient with the grid drawn over it. One
/// `Canvas`, no images -- the same way the overlay draws its own.
struct Sheet: View {
    var body: some View {
        ZStack {
            RadialGradient(colors: [Color.royal, Color.royalDeep],
                           center: .top, startRadius: 0, endRadius: 260)
            Canvas { ctx, size in
                let step = 18.0
                var path = Path()
                var x = 0.0
                while x <= size.width {
                    path.move(to: CGPoint(x: x, y: 0))
                    path.addLine(to: CGPoint(x: x, y: size.height))
                    x += step
                }
                var y = 0.0
                while y <= size.height {
                    path.move(to: CGPoint(x: 0, y: y))
                    path.addLine(to: CGPoint(x: size.width, y: y))
                    y += step
                }
                ctx.stroke(path, with: .color(Color.paper.opacity(0.085)), lineWidth: 0.5)
            }
        }
        .ignoresSafeArea()
    }
}

/// The heart, in code, as the page draws it. It beats at the rate it is
/// given, and sits still when there is no rate.
struct Pulse: View {
    let bpm: Int?
    @State private var big = false

    private var beat: Double { Double(60) / Double(max(40, min(200, bpm ?? 60))) }

    var body: some View {
        Image(systemName: "heart.fill")
            .foregroundStyle(Color.ink)
            .scaleEffect(big ? 1.0 : 0.82)
            .animation(bpm == nil ? nil : .easeInOut(duration: beat / 2).repeatForever(),
                       value: big)
            .onAppear { big = bpm != nil }
            // Rebuilt on every reading, so a changed rate restarts the beat
            // at the new duration instead of keeping the old one forever.
            .id(bpm ?? 0)
    }
}
