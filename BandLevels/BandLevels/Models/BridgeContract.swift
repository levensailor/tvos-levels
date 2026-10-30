import Foundation

/// Version 1 of the bridge wire contract. Mirrors `level_bridge/models.py`.
enum BridgeContract {
    static let schemaVersion = 1
    static let slotCount = 16
    static let slotsPerRow = 8
    static let trackNameMaxLength = 32
    static let trackIdMaxLength = 32

    static let metricDbMinimum = -200.0
    static let gainRange = 0.0...1.0
    static let vuRange = metricDbMinimum...30.0
    static let dbfsRange = metricDbMinimum...6.0
    static let lufsRange = metricDbMinimum...6.0

    /// Matches `^[a-z0-9][a-z0-9_-]{0,31}$`.
    static func isValidTrackId(_ value: String) -> Bool {
        guard let first = value.unicodeScalars.first, value.unicodeScalars.count <= trackIdMaxLength else {
            return false
        }
        let alphanumeric = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyz0123456789")
        let allowed = alphanumeric.union(CharacterSet(charactersIn: "_-"))
        return alphanumeric.contains(first) && value.unicodeScalars.allSatisfy(allowed.contains)
    }
}

struct BridgePeriods: Codable, Equatable, Sendable {
    var dbfsPeakWindowMs: Int
    var vuIntegrationMs: Int
    var lufsWindowMs: Int
    var logicPollMs: Int
    var publishIntervalMs: Int
    var staleAfterMs: Int

    enum CodingKeys: String, CodingKey {
        case dbfsPeakWindowMs = "dbfs_peak_window_ms"
        case vuIntegrationMs = "vu_integration_ms"
        case lufsWindowMs = "lufs_window_ms"
        case logicPollMs = "logic_poll_ms"
        case publishIntervalMs = "publish_interval_ms"
        case staleAfterMs = "stale_after_ms"
    }

    subscript(field: PeriodField) -> Int {
        get {
            switch field {
            case .dbfsPeakWindow: dbfsPeakWindowMs
            case .vuIntegration: vuIntegrationMs
            case .lufsWindow: lufsWindowMs
            case .logicPoll: logicPollMs
            case .publishInterval: publishIntervalMs
            case .staleAfter: staleAfterMs
            }
        }
        set {
            switch field {
            case .dbfsPeakWindow: dbfsPeakWindowMs = newValue
            case .vuIntegration: vuIntegrationMs = newValue
            case .lufsWindow: lufsWindowMs = newValue
            case .logicPoll: logicPollMs = newValue
            case .publishInterval: publishIntervalMs = newValue
            case .staleAfter: staleAfterMs = newValue
            }
        }
    }

    func validationError() -> String? {
        for field in PeriodField.allCases where !field.range.contains(self[field]) {
            return "\(field.wireName) \(self[field]) is outside \(field.range.lowerBound)...\(field.range.upperBound) ms"
        }
        return nil
    }
}

/// Bridge-side measurement and update periods the dashboard can tune.
enum PeriodField: String, CaseIterable, Identifiable, Sendable {
    case dbfsPeakWindow
    case vuIntegration
    case lufsWindow
    case logicPoll
    case publishInterval
    case staleAfter

    var id: String { rawValue }

    var title: String {
        switch self {
        case .dbfsPeakWindow: "dBFS peak window"
        case .vuIntegration: "VU integration"
        case .lufsWindow: "LUFS window"
        case .logicPoll: "Logic gain poll"
        case .publishInterval: "Bridge publish interval"
        case .staleAfter: "Mark stale after"
        }
    }

    var wireName: String { codingKey.stringValue }

    private var codingKey: BridgePeriods.CodingKeys {
        switch self {
        case .dbfsPeakWindow: .dbfsPeakWindowMs
        case .vuIntegration: .vuIntegrationMs
        case .lufsWindow: .lufsWindowMs
        case .logicPoll: .logicPollMs
        case .publishInterval: .publishIntervalMs
        case .staleAfter: .staleAfterMs
        }
    }

    var range: ClosedRange<Int> {
        switch self {
        case .dbfsPeakWindow, .vuIntegration: 50...10_000
        case .lufsWindow: 100...10_000
        case .logicPoll: 250...60_000
        case .publishInterval: 50...5_000
        case .staleAfter: 500...600_000
        }
    }

    private var presets: [Int] {
        switch self {
        case .dbfsPeakWindow, .vuIntegration: [50, 100, 150, 300, 500, 1_000, 3_000]
        case .lufsWindow: [100, 200, 400, 1_000, 3_000, 10_000]
        case .logicPoll: [250, 500, 1_000, 2_000, 5_000, 10_000]
        case .publishInterval: [50, 100, 200, 250, 500, 1_000]
        case .staleAfter: [1_000, 2_000, 3_000, 5_000, 10_000, 30_000]
        }
    }

    /// Picker choices, always including the bridge's current value.
    func options(including current: Int) -> [Int] {
        Set(presets + (range.contains(current) ? [current] : [])).sorted()
    }
}

struct BridgeSource: Decodable, Equatable, Sendable, Identifiable {
    let name: String
    let enabled: Bool
    let connected: Bool
    let detail: String

    var id: String { name }
}

struct BridgeTrack: Decodable, Equatable, Sendable, Identifiable {
    let slot: Int
    let trackId: String
    let name: String
    let gain: Double?
    let vu: Double?
    let dbfs: Double?
    let lufs: Double?
    let updatedAt: String?
    let stale: Bool

    var id: Int { slot }

    enum CodingKeys: String, CodingKey {
        case slot
        case trackId = "track_id"
        case name, gain, vu, dbfs, lufs
        case updatedAt = "updated_at"
        case stale
    }
}

struct BridgeSnapshot: Decodable, Equatable, Sendable {
    let schemaVersion: Int
    let sequence: Int
    let generatedAt: String
    let slotCount: Int
    let periods: BridgePeriods
    let sources: [BridgeSource]
    let tracks: [BridgeTrack]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case sequence
        case generatedAt = "generated_at"
        case slotCount = "slot_count"
        case periods, sources, tracks
    }
}

struct PayloadRejection: Error, Equatable, CustomStringConvertible {
    let reason: String
    var description: String { reason }
}

enum SnapshotDecoder {
    static func decode(_ data: Data) throws -> BridgeSnapshot {
        let snapshot: BridgeSnapshot
        do {
            snapshot = try JSONDecoder().decode(BridgeSnapshot.self, from: data)
        } catch {
            throw PayloadRejection(reason: "malformed snapshot: \(describe(error))")
        }
        try validate(snapshot)
        return snapshot
    }

    static func decodePeriods(_ data: Data) throws -> BridgePeriods {
        let periods: BridgePeriods
        do {
            periods = try JSONDecoder().decode(BridgePeriods.self, from: data)
        } catch {
            throw PayloadRejection(reason: "malformed periods: \(describe(error))")
        }
        if let problem = periods.validationError() {
            throw PayloadRejection(reason: problem)
        }
        return periods
    }

    static func validate(_ snapshot: BridgeSnapshot) throws {
        guard snapshot.schemaVersion == BridgeContract.schemaVersion else {
            throw PayloadRejection(reason: "unsupported schema_version \(snapshot.schemaVersion)")
        }
        guard snapshot.slotCount == BridgeContract.slotCount else {
            throw PayloadRejection(reason: "slot_count must be \(BridgeContract.slotCount), got \(snapshot.slotCount)")
        }
        guard snapshot.sequence >= 0 else {
            throw PayloadRejection(reason: "sequence must not be negative")
        }
        guard isTimestamp(snapshot.generatedAt) else {
            throw PayloadRejection(reason: "generated_at is not an ISO 8601 timestamp")
        }
        if let problem = snapshot.periods.validationError() {
            throw PayloadRejection(reason: problem)
        }
        guard snapshot.tracks.count <= BridgeContract.slotCount else {
            throw PayloadRejection(reason: "too many tracks: \(snapshot.tracks.count)")
        }
        var slots = Set<Int>()
        var ids = Set<String>()
        for track in snapshot.tracks {
            try validate(track)
            guard slots.insert(track.slot).inserted else {
                throw PayloadRejection(reason: "duplicate slot \(track.slot)")
            }
            guard ids.insert(track.trackId).inserted else {
                throw PayloadRejection(reason: "duplicate track_id \(track.trackId)")
            }
        }
    }

    private static func validate(_ track: BridgeTrack) throws {
        guard (1...BridgeContract.slotCount).contains(track.slot) else {
            throw PayloadRejection(reason: "slot \(track.slot) is outside 1...\(BridgeContract.slotCount)")
        }
        guard BridgeContract.isValidTrackId(track.trackId) else {
            throw PayloadRejection(reason: "slot \(track.slot) has invalid track_id")
        }
        let name = track.name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty, track.name.count <= BridgeContract.trackNameMaxLength else {
            throw PayloadRejection(reason: "slot \(track.slot) has invalid name")
        }
        let checks: [(String, Double?, ClosedRange<Double>)] = [
            ("gain", track.gain, BridgeContract.gainRange),
            ("vu", track.vu, BridgeContract.vuRange),
            ("dbfs", track.dbfs, BridgeContract.dbfsRange),
            ("lufs", track.lufs, BridgeContract.lufsRange),
        ]
        for (label, value, range) in checks {
            if let value, !(value.isFinite && range.contains(value)) {
                throw PayloadRejection(reason: "slot \(track.slot) \(label) \(value) is outside \(range)")
            }
        }
        if let updatedAt = track.updatedAt, !isTimestamp(updatedAt) {
            throw PayloadRejection(reason: "slot \(track.slot) updated_at is not an ISO 8601 timestamp")
        }
    }

    static func isTimestamp(_ text: String) -> Bool {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if formatter.date(from: text) != nil { return true }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: text) != nil
    }

    private static func describe(_ error: Error) -> String {
        switch error {
        case DecodingError.keyNotFound(let key, _):
            "missing \(key.stringValue)"
        case DecodingError.typeMismatch(_, let context), DecodingError.valueNotFound(_, let context):
            "wrong type at \(context.codingPath.map(\.stringValue).joined(separator: "."))"
        case DecodingError.dataCorrupted(let context):
            context.debugDescription
        default:
            error.localizedDescription
        }
    }
}
