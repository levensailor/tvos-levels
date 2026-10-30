import Foundation
import Observation

/// Viewer preferences and bridge connection identifiers, persisted in UserDefaults.
/// Defaults come from Info.plist keys populated by `Config/Base.xcconfig`.
@Observable
@MainActor
final class AppSettings {
    enum InfoKey {
        static let host = "BandLevelsBridgeHost"
        static let port = "BandLevelsBridgePort"
        static let streamPath = "BandLevelsStreamPath"
        static let periodsPath = "BandLevelsPeriodsPath"
    }

    enum StorageKey {
        static let host = "bridgeHost"
        static let port = "bridgePort"
        static let streamPath = "streamPath"
        static let periodsPath = "periodsPath"
        static let emphasis = "emphasis"
        static let displayRefresh = "displayRefreshMilliseconds"
    }

    static let fallbackHost = "localhost"
    static let fallbackPort = 8000
    static let fallbackStreamPath = "/api/v1/stream"
    static let fallbackPeriodsPath = "/api/v1/periods"
    static let displayRefreshOptions = [50, 100, 150, 250, 500, 1_000, 2_000]
    static let defaultDisplayRefresh = 100
    static let portRange = 1...65_535

    var bridgeHost: String { didSet { defaults.set(bridgeHost, forKey: StorageKey.host) } }
    var bridgePort: Int { didSet { defaults.set(bridgePort, forKey: StorageKey.port) } }
    var streamPath: String { didSet { defaults.set(streamPath, forKey: StorageKey.streamPath) } }
    var periodsPath: String { didSet { defaults.set(periodsPath, forKey: StorageKey.periodsPath) } }
    var emphasis: MetricKind { didSet { defaults.set(emphasis.rawValue, forKey: StorageKey.emphasis) } }
    var displayRefreshMilliseconds: Int {
        didSet { defaults.set(displayRefreshMilliseconds, forKey: StorageKey.displayRefresh) }
    }

    @ObservationIgnored private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard, bundle: Bundle = .main) {
        self.defaults = defaults
        func info(_ key: String) -> String? {
            (bundle.object(forInfoDictionaryKey: key) as? String)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .nonEmpty
        }
        bridgeHost = defaults.string(forKey: StorageKey.host) ?? info(InfoKey.host) ?? Self.fallbackHost
        let storedPort = defaults.integer(forKey: StorageKey.port)
        bridgePort = Self.portRange.contains(storedPort)
            ? storedPort
            : Int(info(InfoKey.port) ?? "").flatMap { Self.portRange.contains($0) ? $0 : nil } ?? Self.fallbackPort
        streamPath = defaults.string(forKey: StorageKey.streamPath) ?? info(InfoKey.streamPath) ?? Self.fallbackStreamPath
        periodsPath = defaults.string(forKey: StorageKey.periodsPath) ?? info(InfoKey.periodsPath) ?? Self.fallbackPeriodsPath
        emphasis = defaults.string(forKey: StorageKey.emphasis).flatMap(MetricKind.init(rawValue:)) ?? .vu
        let storedRefresh = defaults.integer(forKey: StorageKey.displayRefresh)
        displayRefreshMilliseconds = Self.displayRefreshOptions.contains(storedRefresh)
            ? storedRefresh
            : Self.defaultDisplayRefresh
    }

    var streamURL: URL? { url(scheme: "ws", path: streamPath) }
    var periodsURL: URL? { url(scheme: "http", path: periodsPath) }

    /// Returns a reason when the connection settings cannot form valid URLs.
    var connectionProblem: String? {
        if bridgeHost.isEmpty { return "Bridge host is empty" }
        if !Self.portRange.contains(bridgePort) { return "Port must be 1–65535" }
        if !streamPath.hasPrefix("/") || !periodsPath.hasPrefix("/") { return "Paths must start with /" }
        if streamURL == nil || periodsURL == nil { return "Host or path is not a valid URL component" }
        return nil
    }

    private func url(scheme: String, path: String) -> URL? {
        guard !bridgeHost.isEmpty, Self.portRange.contains(bridgePort), path.hasPrefix("/") else { return nil }
        var components = URLComponents()
        components.scheme = scheme
        components.host = bridgeHost
        components.port = bridgePort
        components.path = path
        return components.url
    }
}

private extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}
