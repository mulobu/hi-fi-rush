import Foundation
import HealthKit

/// The sensor.
///
/// An `HKWorkoutSession` with an `HKLiveWorkoutBuilder` is the only thing on
/// watchOS that keeps the heart-rate sensor on and this app running with the
/// wrist down (ADR 0028). Readings arrive about every 5 s, sometimes later,
/// and there is no way to ask for more.
///
/// The workout is **discarded**, never saved: this is a readout, not a
/// training log, and a five-hour "Other" workout every stream is not what
/// the user asked for. The session still holds the sensor open while it
/// runs; what discarding drops is the record afterwards.
@MainActor
final class Monitor: NSObject, ObservableObject {
    @Published private(set) var bpm: Int?
    @Published private(set) var at: Date?
    @Published private(set) var running = false
    @Published private(set) var readings = 0
    @Published private(set) var problem: String?
    /// True on the simulator, where the numbers are watchOS's own synthetic
    /// workout data rather than a wrist. The screen says so, so a screenshot
    /// of a test can never be mistaken for a real reading.
    let simulated: Bool = {
        #if targetEnvironment(simulator)
        return true
        #else
        return false
        #endif
    }()

    /// Every reading, on the main actor. `Feed` posts it.
    var onReading: ((Int, Date) -> Void)?

    private let store = HKHealthStore()
    private let hr = HKQuantityType(.heartRate)
    private let unit = HKUnit.count().unitDivided(by: .minute())
    private var session: HKWorkoutSession?
    private var builder: HKLiveWorkoutBuilder?

    var since: TimeInterval? { at.map { -$0.timeIntervalSinceNow } }

    func start() async {
        problem = nil
        guard HKHealthStore.isHealthDataAvailable() else {
            problem = "no Health data on this device"
            return
        }
        // Workouts are shared, heart rate is read. A workout session needs
        // the share half even though nothing is ever saved.
        do {
            try await store.requestAuthorization(toShare: [HKQuantityType.workoutType()], read: [hr])
        } catch {
            problem = "Health access: \(error.localizedDescription)"
            return
        }

        let cfg = HKWorkoutConfiguration()
        cfg.activityType = .other
        cfg.locationType = .indoor
        do {
            let s = try HKWorkoutSession(healthStore: store, configuration: cfg)
            let b = s.associatedWorkoutBuilder()
            let source = HKLiveWorkoutDataSource(healthStore: store, workoutConfiguration: cfg)
            // Named rather than left to the configuration's defaults: heart
            // rate is the whole point, and a default set is not a promise.
            source.enableCollection(for: hr, predicate: nil)
            b.dataSource = source
            s.delegate = self
            b.delegate = self
            let begin = Date()
            s.startActivity(with: begin)
            try await b.beginCollection(at: begin)
            session = s
            builder = b
            running = true
        } catch {
            problem = "workout: \(error.localizedDescription)"
        }
    }

    func stop() async {
        running = false
        guard let s = session, let b = builder else { return }
        session = nil
        builder = nil
        s.end()
        try? await b.endCollection(at: Date())
        b.discardWorkout()
    }

    fileprivate func got(_ value: Int, _ when: Date) {
        // The bridge's own range (20-250): a number outside it would be
        // refused there anyway, so it never leaves the wrist.
        guard (20...250).contains(value) else { return }
        bpm = value
        at = when
        readings += 1
        onReading?(value, when)
    }

    fileprivate func failed(_ text: String) {
        problem = text
        running = false
    }
}

extension Monitor: HKLiveWorkoutBuilderDelegate {
    nonisolated func workoutBuilder(_ builder: HKLiveWorkoutBuilder,
                                    didCollectDataOf types: Set<HKSampleType>) {
        let hr = HKQuantityType(.heartRate)
        guard types.contains(hr),
              let stats = builder.statistics(for: hr),
              let quantity = stats.mostRecentQuantity()
        else { return }
        let value = quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))
        let when = stats.mostRecentQuantityDateInterval()?.end ?? Date()
        Task { @MainActor in self.got(Int(value.rounded()), when) }
    }

    nonisolated func workoutBuilderDidCollectEvent(_ builder: HKLiveWorkoutBuilder) {}
}

extension Monitor: HKWorkoutSessionDelegate {
    nonisolated func workoutSession(_ session: HKWorkoutSession,
                                    didChangeTo toState: HKWorkoutSessionState,
                                    from: HKWorkoutSessionState,
                                    date: Date) {
        Task { @MainActor in
            switch toState {
            case .running, .prepared, .paused: self.running = true
            default: self.running = false
            }
        }
    }

    nonisolated func workoutSession(_ session: HKWorkoutSession, didFailWithError error: Error) {
        Task { @MainActor in self.failed("workout stopped: \(error.localizedDescription)") }
    }
}
