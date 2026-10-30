import Foundation

/// The four standard metric views a viewer can emphasize.
enum MetricKind: String, CaseIterable, Identifiable, Sendable {
    case gain
    case vu
    case dbfs
    case lufs

    var id: String { rawValue }

    var title: String {
        switch self {
        case .gain: "Gain"
        case .vu: "VU"
        case .dbfs: "dBFS"
        case .lufs: "LUFS"
        }
    }

    var unit: String {
        switch self {
        case .gain: "fader"
        case .vu: "VU"
        case .dbfs: "dBFS peak"
        case .lufs: "LUFS M"
        }
    }

    /// Range drawn by the meter bar; values outside are clamped.
    var meterRange: ClosedRange<Double> {
        switch self {
        case .gain: 0...1
        case .vu: -20...3
        case .dbfs: -60...0
        case .lufs: -60...0
        }
    }

    func value(in track: BridgeTrack) -> Double? {
        switch self {
        case .gain: track.gain
        case .vu: track.vu
        case .dbfs: track.dbfs
        case .lufs: track.lufs
        }
    }

    func formatted(_ value: Double?) -> String {
        guard let value else { return "—" }
        switch self {
        case .gain:
            return "\(Int((value * 100).rounded()))%"
        case .vu where value > 0:
            return "+" + value.formatted(.number.precision(.fractionLength(1)))
        default:
            return value.formatted(.number.precision(.fractionLength(1)))
        }
    }

    func normalized(_ value: Double?) -> Double {
        guard let value, value.isFinite else { return 0 }
        let span = meterRange.upperBound - meterRange.lowerBound
        return min(max((value - meterRange.lowerBound) / span, 0), 1)
    }
}
