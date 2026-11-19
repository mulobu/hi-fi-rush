import SwiftUI

/// Heart Rate -- the wrist half of ADR 0028.
///
///     watch (this app) --POST /hr--> heart/heart-bridge.py :4462
///                                      --SSE /events--> the overlay pages
///
/// It does one thing: hold an `HKWorkoutSession` open so the sensor keeps
/// reporting, and post every reading to the bridge on the PC.
@main
struct HeartRateApp: App {
    @StateObject private var feed = Feed()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(feed)
        }
    }
}

/// The wiring: the sensor's readings go straight out to the bridge.
///
/// `Monitor` does not know the bridge exists and `Poster` does not know
/// where a number came from, so a reading invented on the simulator and one
/// off the wrist travel the identical path.
@MainActor
final class Feed: ObservableObject {
    let monitor = Monitor()
    let poster = Poster()

    @Published var host: String {
        didSet { Config.host = host }
    }

    /// The address is set but unusable -- a half-typed one, most likely.
    var addressBad: Bool { !host.isEmpty && Config.url(path: "/hr", host: host) == nil }

    init() {
        host = Config.host
        monitor.onReading = { [weak self] bpm, at in
            guard let self, let url = Config.url(path: "/hr", host: self.host) else { return }
            self.poster.post(bpm: bpm, at: at, to: url)
        }
    }

    func start() async { await monitor.start() }
    func stop() async { await monitor.stop() }
}
