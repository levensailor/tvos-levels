import Foundation
@testable import BandLevels

enum Fixtures {
    static let trackNames = [
        "VOX", "BGV 1", "BGV 2", "GUITAR 1", "GUITAR 2", "BASS", "KEYS",
        "KICK", "SNARE", "HI-HAT", "TOM 1", "TOM 2", "OVERHEADS",
    ]

    static func trackJSON(slot: Int, name: String, gain: String = "null", lufs: String = "null") -> String {
        let id = name.lowercased().replacingOccurrences(of: " ", with: "-")
        return """
        {"slot": \(slot), "track_id": "\(id)", "name": "\(name)", "gain": \(gain), "vu": -3.2,
         "dbfs": -9.1, "lufs": \(lufs), "updated_at": "2026-10-30T10:40:00.123-04:00", "stale": false}
        """
    }

    static func snapshotJSON(
        tracks: [String]? = nil,
        schemaVersion: Int = 1,
        slotCount: Int = 16,
        sequence: Int = 7,
        publishInterval: Int = 100
    ) -> Data {
        let rows = tracks ?? trackNames.enumerated().map { trackJSON(slot: $0.offset + 1, name: $0.element) }
        let json = """
        {
          "schema_version": \(schemaVersion),
          "sequence": \(sequence),
          "generated_at": "2026-10-30T10:40:00.456-04:00",
          "slot_count": \(slotCount),
          "periods": {"dbfs_peak_window_ms": 300, "vu_integration_ms": 300, "lufs_window_ms": 400,
                      "logic_poll_ms": 1000, "publish_interval_ms": \(publishInterval), "stale_after_ms": 3000},
          "sources": [{"name": "json", "enabled": true, "connected": true, "detail": "ok"}],
          "tracks": [\(rows.joined(separator: ","))]
        }
        """
        return Data(json.utf8)
    }
}
