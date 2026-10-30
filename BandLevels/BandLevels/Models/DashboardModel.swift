import Foundation
import Observation

struct DashboardSlot: Identifiable, Equatable, Sendable {
    let number: Int
    let track: BridgeTrack?

    var id: Int { number }
    var isPopulated: Bool { track != nil }
}

enum ConnectionState: Equatable, Sendable {
    case idle
    case connecting
    case connected
    case disconnected(String)
    case misconfigured(String)

    var label: String {
        switch self {
        case .idle: "Idle"
        case .connecting: "Connecting"
        case .connected: "Live"
        case .disconnected(let reason): "Offline — \(reason)"
        case .misconfigured(let reason): "Check settings — \(reason)"
        }
    }

    var isLive: Bool { self == .connected }
}

/// Dashboard state: 16 fixed slots fed by validated bridge snapshots over a WebSocket.
@Observable
@MainActor
final class DashboardModel {
    static let maxReconnectDelaySeconds = 15.0
    static let misconfiguredRetrySeconds = 2.0

    private(set) var slots: [DashboardSlot] = DashboardModel.emptySlots()
    private(set) var connection: ConnectionState = .idle
    private(set) var periods: BridgePeriods?
    private(set) var sources: [BridgeSource] = []
    private(set) var sequence: Int?
    private(set) var lastRejection: String?
    private(set) var periodsStatus: String?
    private(set) var acceptedSnapshots = 0
    private(set) var rejectedPayloads = 0

    let settings: AppSettings

    @ObservationIgnored private var pendingSnapshot: BridgeSnapshot?
    @ObservationIgnored private var currentSocket: URLSessionWebSocketTask?
    @ObservationIgnored private var reconnectRequested = false
    @ObservationIgnored private let session: URLSession

    init(settings: AppSettings, session: URLSession = .shared) {
        self.settings = settings
        self.session = session
    }

    nonisolated static func emptySlots() -> [DashboardSlot] {
        (1...BridgeContract.slotCount).map { DashboardSlot(number: $0, track: nil) }
    }

    var rows: [[DashboardSlot]] {
        stride(from: 0, to: slots.count, by: BridgeContract.slotsPerRow).map {
            Array(slots[$0..<min($0 + BridgeContract.slotsPerRow, slots.count)])
        }
    }

    var populatedCount: Int { slots.filter(\.isPopulated).count }

    // MARK: Ingest

    /// Validates a raw payload; valid snapshots wait for the next display refresh.
    @discardableResult
    func ingest(_ data: Data) -> Bool {
        do {
            pendingSnapshot = try SnapshotDecoder.decode(data)
            return true
        } catch {
            let reason = (error as? PayloadRejection)?.reason ?? error.localizedDescription
            rejectedPayloads += 1
            lastRejection = reason
            AppLog.warning(AppLog.bridge, "Rejected bridge payload: \(reason)")
            return false
        }
    }

    func applyPendingSnapshot() {
        guard let snapshot = pendingSnapshot else { return }
        pendingSnapshot = nil
        apply(snapshot)
    }

    func apply(_ snapshot: BridgeSnapshot) {
        let bySlot = Dictionary(uniqueKeysWithValues: snapshot.tracks.map { ($0.slot, $0) })
        let updated = (1...BridgeContract.slotCount).map { DashboardSlot(number: $0, track: bySlot[$0]) }
        if updated != slots { slots = updated }
        if periods != snapshot.periods { periods = snapshot.periods }
        if sources != snapshot.sources { sources = snapshot.sources }
        sequence = snapshot.sequence
        acceptedSnapshots += 1
    }

    // MARK: Connection

    func run() async {
        async let stream: Void = streamLoop()
        async let display: Void = displayLoop()
        _ = await (stream, display)
    }

    /// Drops the current socket so the stream loop reconnects with the latest settings.
    func reconnect() {
        reconnectRequested = true
        currentSocket?.cancel(with: .goingAway, reason: nil)
    }

    private func displayLoop() async {
        while !Task.isCancelled {
            applyPendingSnapshot()
            try? await Task.sleep(for: .milliseconds(settings.displayRefreshMilliseconds))
        }
    }

    private func streamLoop() async {
        var attempt = 0
        while !Task.isCancelled {
            if let problem = settings.connectionProblem {
                connection = .misconfigured(problem)
                try? await Task.sleep(for: .seconds(Self.misconfiguredRetrySeconds))
                continue
            }
            guard let url = settings.streamURL else { continue }
            let socket = session.webSocketTask(with: url)
            currentSocket = socket
            reconnectRequested = false
            connection = .connecting
            AppLog.info(AppLog.bridge, "Connecting to \(url.absoluteString)")
            socket.resume()
            do {
                while !Task.isCancelled {
                    let data = try await Self.receive(from: socket)
                    if connection != .connected {
                        connection = .connected
                        attempt = 0
                        AppLog.info(AppLog.bridge, "Connected to \(url.absoluteString)")
                    }
                    ingest(data)
                }
            } catch {
                if !Task.isCancelled && !reconnectRequested {
                    connection = .disconnected(error.localizedDescription)
                    AppLog.warning(AppLog.bridge, "Stream ended: \(error.localizedDescription)")
                }
            }
            socket.cancel(with: .goingAway, reason: nil)
            currentSocket = nil
            if reconnectRequested { continue }
            attempt += 1
            let delay = min(Self.maxReconnectDelaySeconds, 0.5 * Double(1 << min(attempt, 5)))
            try? await Task.sleep(for: .seconds(delay))
        }
    }

    nonisolated private static func receive(from socket: URLSessionWebSocketTask) async throws -> Data {
        let message = try await withTaskCancellationHandler {
            try await socket.receive()
        } onCancel: {
            socket.cancel(with: .goingAway, reason: nil)
        }
        switch message {
        case .string(let text): return Data(text.utf8)
        case .data(let data): return data
        @unknown default: throw PayloadRejection(reason: "unsupported WebSocket message")
        }
    }

    // MARK: Periods

    func applyPeriods(_ requested: BridgePeriods) async {
        if let problem = requested.validationError() {
            periodsStatus = "Not sent: \(problem)"
            return
        }
        guard let url = settings.periodsURL else {
            periodsStatus = settings.connectionProblem ?? "Invalid bridge address"
            return
        }
        let body: Data
        do {
            body = try JSONEncoder().encode(requested)
        } catch {
            periodsStatus = "Could not encode periods"
            return
        }
        periodsStatus = "Sending…"
        do {
            let (data, status) = try await Self.put(body, to: url, using: session)
            guard status == 200 else {
                let detail = String(decoding: data, as: UTF8.self).prefix(160)
                periodsStatus = "Bridge rejected periods (HTTP \(status)): \(detail)"
                AppLog.warning(AppLog.bridge, "Periods rejected with HTTP \(status)")
                return
            }
            let accepted = try SnapshotDecoder.decodePeriods(data)
            periods = accepted
            periodsStatus = "Applied to bridge"
            AppLog.info(AppLog.bridge, "Periods applied")
        } catch let rejection as PayloadRejection {
            periodsStatus = "Bridge reply rejected: \(rejection.reason)"
            AppLog.warning(AppLog.bridge, "Periods reply rejected: \(rejection.reason)")
        } catch {
            periodsStatus = "Could not reach bridge: \(error.localizedDescription)"
            AppLog.warning(AppLog.bridge, "Periods request failed: \(error.localizedDescription)")
        }
    }

    nonisolated private static func put(_ body: Data, to url: URL, using session: URLSession) async throws -> (Data, Int) {
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = body
        let (data, response) = try await session.data(for: request)
        return (data, (response as? HTTPURLResponse)?.statusCode ?? 0)
    }
}
