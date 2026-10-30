import Foundation
import Testing
@testable import BandLevels

@Suite("Bridge snapshot validation")
struct SnapshotDecoderTests {
    @Test func decodesValidSnapshot() throws {
        let snapshot = try SnapshotDecoder.decode(Fixtures.snapshotJSON())
        #expect(snapshot.slotCount == 16)
        #expect(snapshot.tracks.count == 13)
        #expect(snapshot.tracks.first?.name == "VOX")
        #expect(snapshot.periods.lufsWindowMs == 400)
    }

    @Test(arguments: [
        ("schema", Fixtures.snapshotJSON(schemaVersion: 2)),
        ("slot count", Fixtures.snapshotJSON(slotCount: 12)),
        ("negative sequence", Fixtures.snapshotJSON(sequence: -1)),
        ("period range", Fixtures.snapshotJSON(publishInterval: 5)),
        ("slot 17", Fixtures.snapshotJSON(tracks: [Fixtures.trackJSON(slot: 17, name: "VOX")])),
        ("duplicate slot", Fixtures.snapshotJSON(tracks: [
            Fixtures.trackJSON(slot: 1, name: "VOX"), Fixtures.trackJSON(slot: 1, name: "BASS"),
        ])),
        ("gain range", Fixtures.snapshotJSON(tracks: [Fixtures.trackJSON(slot: 1, name: "VOX", gain: "1.5")])),
        ("lufs range", Fixtures.snapshotJSON(tracks: [Fixtures.trackJSON(slot: 1, name: "VOX", lufs: "12")])),
        ("blank name", Fixtures.snapshotJSON(tracks: [Fixtures.trackJSON(slot: 1, name: " ")])),
        ("wrong type", Fixtures.snapshotJSON(tracks: [Fixtures.trackJSON(slot: 1, name: "VOX", gain: "\"loud\"")])),
        ("malformed", Data("{\"schema_version\": 1, ".utf8)),
    ])
    func rejectsInvalidPayload(label: String, data: Data) {
        #expect(throws: PayloadRejection.self, "\(label) should be rejected") {
            try SnapshotDecoder.decode(data)
        }
    }

    @Test func trackIdValidationMatchesBridgePattern() {
        #expect(BridgeContract.isValidTrackId("guitar-1"))
        #expect(BridgeContract.isValidTrackId("hi_hat"))
        #expect(!BridgeContract.isValidTrackId("VOX"))
        #expect(!BridgeContract.isValidTrackId("-vox"))
        #expect(!BridgeContract.isValidTrackId(""))
        #expect(!BridgeContract.isValidTrackId(String(repeating: "a", count: 33)))
    }
}
