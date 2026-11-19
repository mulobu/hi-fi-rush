import Foundation

/// POSTs one reading to the bridge: `{"bpm": 128, "at": 1730000000000}`.
///
/// **There is no retry and no queue, deliberately.** The page judges a
/// reading stale by its own clock, from when it arrived, never by the
/// watch's `at` (ADR 0028) -- so a reading delivered late would show as
/// current, which is worse than one that never arrives. The next sample is
/// about 5 s away and the timeout is shorter than that, so a dropped post
/// costs one beat of the readout and nothing else.
///
/// One request in flight at a time, for the same reason: a backed-up
/// request is a stale reading waiting to be believed.
@MainActor
final class Poster: ObservableObject {
    enum Outcome: Equatable {
        case idle
        case sending
        case ok
        case dropped            // a post was still in flight
        case failed(String)

        var line: String {
            switch self {
            case .idle: return "not sending yet"
            case .sending: return "sending"
            case .ok: return "bridge has it"
            case .dropped: return "skipped one"
            case .failed(let why): return why
            }
        }

        var bad: Bool {
            if case .failed = self { return true }
            return false
        }
    }

    @Published private(set) var outcome: Outcome = .idle
    @Published private(set) var sent = 0
    @Published private(set) var lost = 0

    private var busy = false

    private let session: URLSession = {
        let c = URLSessionConfiguration.ephemeral
        // Shorter than the ~5 s between readings, so a request can never
        // outlive the reading it carries.
        c.timeoutIntervalForRequest = 4
        c.timeoutIntervalForResource = 4
        c.waitsForConnectivity = false
        c.httpShouldUsePipelining = true
        return URLSession(configuration: c)
    }()

    func post(bpm: Int, at: Date, to url: URL) {
        guard !busy else {
            lost += 1
            outcome = .dropped
            return
        }
        busy = true
        outcome = .sending
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = Data(#"{"bpm":\#(bpm),"at":\#(Int(at.timeIntervalSince1970 * 1000))}"#.utf8)
        Task { await run(req) }
    }

    /// `GET /status`, for the settings screen. It proves the address reaches
    /// the bridge **without** posting a number: a test reading would show on
    /// stream as live for the next 15 s.
    func check(_ url: URL) async -> String {
        do {
            let (data, resp) = try await session.data(for: URLRequest(url: url))
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            guard (200...299).contains(code) else { return "bridge said \(code)" }
            let d = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            let pages = (d?["clients"] as? Int) ?? 0
            let last = (d?["age"] as? Int).map { "last reading \($0 / 1000)s ago" } ?? "no reading yet"
            return "bridge found. \(last), \(pages) page\(pages == 1 ? "" : "s") listening"
        } catch {
            return Self.why(error)
        }
    }

    private func run(_ req: URLRequest) async {
        defer { busy = false }
        do {
            let (data, resp) = try await session.data(for: req)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            if (200...299).contains(code) {
                sent += 1
                outcome = .ok
            } else {
                lost += 1
                // A 400 carries the bridge's own words -- show those.
                let d = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
                outcome = .failed((d?["error"] as? String) ?? "bridge said \(code)")
            }
        } catch {
            lost += 1
            outcome = .failed(Self.why(error))
        }
    }

    /// A watch screen has room for about four words.
    private static func why(_ error: Error) -> String {
        guard let e = error as? URLError else { return error.localizedDescription }
        switch e.code {
        case .cannotConnectToHost: return "nothing on that port"
        case .cannotFindHost: return "no such address"
        case .timedOut: return "timed out"
        case .notConnectedToInternet: return "watch is offline"
        case .networkConnectionLost: return "connection lost"
        case .appTransportSecurityRequiresSecureConnection: return "blocked: http not allowed"
        default: return e.localizedDescription
        }
    }
}
