import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var feed: Feed

    var body: some View {
        NavigationStack {
            Readout(feed: feed, monitor: feed.monitor, poster: feed.poster)
                .background(Sheet())
        }
    }
}

/// The one screen: the number, whether the bridge is getting it, the
/// switch, and the way to the address.
private struct Readout: View {
    @ObservedObject var feed: Feed
    @ObservedObject var monitor: Monitor
    @ObservedObject var poster: Poster

    var body: some View {
        ScrollView {
            VStack(spacing: 5) {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Pulse(bpm: monitor.running ? monitor.bpm : nil)
                        .font(.system(size: 22))
                    Text(monitor.bpm.map(String.init) ?? "--")
                        .font(.system(size: 50, weight: .black, design: .rounded))
                        .foregroundStyle(Color.ink)
                        .contentTransition(.numericText())
                        .animation(.easeOut(duration: 0.2), value: monitor.bpm)
                }
                .padding(.top, 2)

                Text(monitor.simulated ? "SIMULATED BPM" : "BPM")
                    .font(.system(size: 11, weight: .heavy, design: .rounded))
                    .tracking(2)
                    .foregroundStyle(Color.paper.opacity(0.75))

                Divider().overlay(Color.ink.opacity(0.4))

                status

                Button(monitor.running ? "Stop" : "Go Live") {
                    Task { monitor.running ? await feed.stop() : await feed.start() }
                }
                .buttonStyle(.borderedProminent)
                .tint(monitor.running ? Color.royalDeep : Color.ink)
                .foregroundStyle(monitor.running ? Color.paper : Color.royalDeep)
                .font(.system(size: 15, weight: .bold, design: .rounded))

                NavigationLink {
                    AddressView(feed: feed, poster: poster)
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "desktopcomputer")
                        Text(feed.host.isEmpty ? "set the PC's address" : feed.host)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                    }
                    .font(.system(size: 12, weight: .semibold, design: .rounded))
                }
                .foregroundStyle(feed.host.isEmpty || feed.addressBad
                                 ? Color.ink : Color.paper.opacity(0.8))
            }
            .padding(.horizontal, 4)
            .padding(.bottom, 6)
        }
        .navigationTitle("")
    }

    /// One line, in this order of urgency: a sensor or workout fault, then
    /// no address, then a bad address, then how the posting is going.
    @ViewBuilder private var status: some View {
        if let problem = monitor.problem {
            Line(text: problem, bad: true)
        } else if feed.host.isEmpty {
            Line(text: "no address yet -- the bridge prints it", bad: true)
        } else if feed.addressBad {
            Line(text: "that address cannot be used", bad: true)
        } else if !monitor.running {
            Line(text: "sensor off", bad: false)
        } else {
            Line(text: "\(poster.outcome.line) \u{00b7} \(poster.sent) sent", bad: poster.outcome.bad)
        }
    }

    private struct Line: View {
        let text: String
        let bad: Bool

        var body: some View {
            Text(text)
                .font(.system(size: 12, weight: .medium, design: .rounded))
                .multilineTextAlignment(.center)
                .foregroundStyle(bad ? Color.ink : Color.paper.opacity(0.7))
                .padding(.horizontal, 2)
        }
    }
}

/// The address, and a check that does not fake a reading.
private struct AddressView: View {
    @ObservedObject var feed: Feed
    @ObservedObject var poster: Poster

    @State private var typed = ""
    @State private var result: String?
    @State private var checking = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 8) {
                Text("The PC running heart-bridge.py. It prints this when it starts.")
                    .font(.system(size: 12, design: .rounded))
                    .foregroundStyle(Color.paper.opacity(0.7))

                TextField("192.168.1.20", text: $typed)
                    .font(.system(size: 16, weight: .semibold, design: .monospaced))
                    .onSubmit(save)

                Text("Port \(Config.defaultPort) unless you add :port")
                    .font(.system(size: 10, design: .rounded))
                    .foregroundStyle(Color.paper.opacity(0.5))

                Button(checking ? "Checking..." : "Save & Check") { save(); check() }
                    .buttonStyle(.borderedProminent)
                    .tint(Color.ink)
                    .foregroundStyle(Color.royalDeep)
                    .font(.system(size: 14, weight: .bold, design: .rounded))
                    .disabled(checking)

                if let result {
                    Text(result)
                        .font(.system(size: 12, weight: .medium, design: .rounded))
                        .foregroundStyle(Color.paper)
                }
            }
            .padding(.horizontal, 4)
        }
        .background(Sheet())
        .navigationTitle("Bridge")
        .onAppear { typed = feed.host }
    }

    private func save() {
        feed.host = typed.trimmingCharacters(in: .whitespacesAndNewlines)
        typed = feed.host
    }

    /// `GET /status`, never a `POST` -- a test reading would show on stream
    /// as live for the next 15 s.
    private func check() {
        guard let url = Config.url(path: "/status", host: feed.host) else {
            result = feed.host.isEmpty ? "type an address first" : "that address cannot be used"
            return
        }
        checking = true
        result = nil
        Task {
            let answer = await poster.check(url)
            checking = false
            result = answer
        }
    }
}
