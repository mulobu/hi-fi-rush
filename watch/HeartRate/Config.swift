import Foundation

/// Where the bridge is. The one setting this app has.
///
/// `heart/heart-bridge.py` prints the PC's addresses when it starts; that
/// line is what gets typed in on the watch. It is kept in `UserDefaults`,
/// so it survives a relaunch and a reboot -- the watch gets handed a
/// stream, not reconfigured before every one.
enum Config {
    /// `ports.heart` in `core/contract.js`. An address may carry its own
    /// port as `host:port`, which is the escape hatch if the bridge ever
    /// moves; without one this is used.
    static let defaultPort = 4462

    private static let key = "bridgeHost"

    static var host: String {
        get { UserDefaults.standard.string(forKey: key) ?? "" }
        set { UserDefaults.standard.set(clean(newValue), forKey: key) }
    }

    /// `nil` while the address cannot be used, which is what makes an unset
    /// or half-typed address a quiet no-op rather than a request to nowhere.
    /// The field takes `192.168.1.20` or `tower.local`, optionally `:port`;
    /// a scheme, a path or a space is a typo, not an address.
    static func url(path: String, host: String = Config.host) -> URL? {
        let h = clean(host)
        guard !h.isEmpty, !h.contains("/"), !h.contains(" "), !h.contains("@") else { return nil }
        let authority = h.contains(":") ? h : "\(h):\(defaultPort)"
        guard let url = URL(string: "http://\(authority)\(path)"),
              let name = url.host, !name.isEmpty, url.port != nil
        else { return nil }
        return url
    }

    private static func clean(_ s: String) -> String {
        s.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
