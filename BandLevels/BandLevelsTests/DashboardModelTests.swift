import Foundation
import Testing
@testable import BandLevels

@Suite("Dashboard model")
@MainActor
struct DashboardModelTests {
    private func makeModel() -> DashboardModel {
        let defaults = UserDefaults(suiteName: "BandLevelsTests-\(UUID().uuidString)")!
        return DashboardModel(settings: AppSettings(defaults: defaults, bundle: Bundle(for: BundleToken.self)))
    }

    @Test func startsWithSixteenEmptySlotsInTwoRowsOfEight() {
        let model = makeModel()
        #expect(model.slots.count == 16)
        #expect(model.rows.count == 2)
        let rowsHaveEight = model.rows.allSatisfy { $0.count == 8 }
        #expect(rowsHaveEight)
        #expect(model.populatedCount == 0)
    }

    @Test func validSnapshotPopulatesFirstThirteenSlots() {
        let model = makeModel()
        #expect(model.ingest(Fixtures.snapshotJSON()))
        model.applyPendingSnapshot()
        #expect(model.populatedCount == 13)
        let firstThirteenPopulated = model.slots.prefix(13).allSatisfy { $0.isPopulated }
        let lastThreeAvailable = model.slots.suffix(3).allSatisfy { !$0.isPopulated }
        #expect(firstThirteenPopulated)
        #expect(lastThreeAvailable)
        #expect(model.rows[1].map(\.number) == Array(9...16))
        #expect(model.sequence == 7)
    }

    @Test func payloadUpdatesTheMatchingTrackBox() {
        let model = makeModel()
        let tracks = [
            Fixtures.trackJSON(slot: 1, name: "VOX", gain: "0.25"),
            Fixtures.trackJSON(slot: 4, name: "GUITAR 1", gain: "0.8", lufs: "-14.5"),
        ]
        model.ingest(Fixtures.snapshotJSON(tracks: tracks))
        model.applyPendingSnapshot()
        let guitar = model.slots[3].track
        #expect(guitar?.name == "GUITAR 1")
        #expect(guitar?.gain == 0.8)
        #expect(guitar?.lufs == -14.5)
        #expect(model.slots[0].track?.gain == 0.25)
        #expect(model.slots[1].track == nil)
    }

    @Test func invalidPayloadIsRejectedWithoutChangingState() {
        let model = makeModel()
        model.ingest(Fixtures.snapshotJSON())
        model.applyPendingSnapshot()
        let before = model.slots

        #expect(!model.ingest(Fixtures.snapshotJSON(schemaVersion: 9)))
        model.applyPendingSnapshot()
        #expect(model.slots == before)
        #expect(model.rejectedPayloads == 1)
        #expect(model.lastRejection?.contains("schema_version") == true)
    }

    @Test func exposesAllFourMetricsAndTunablePeriods() throws {
        let model = makeModel()
        let tracks = [Fixtures.trackJSON(slot: 1, name: "VOX", gain: "0.5", lufs: "-18.2")]
        model.ingest(Fixtures.snapshotJSON(tracks: tracks))
        model.applyPendingSnapshot()
        let track = try #require(model.slots[0].track)
        #expect(MetricKind.allCases == [.gain, .vu, .dbfs, .lufs])
        let everyMetricPresent = MetricKind.allCases.allSatisfy { $0.value(in: track) != nil }
        #expect(everyMetricPresent)
        let periods = try #require(model.periods)
        #expect(periods.vuIntegrationMs == 300)
        #expect(PeriodField.allCases.count == 6)
        for field in PeriodField.allCases {
            #expect(field.options(including: periods[field]).contains(periods[field]))
        }
    }
}

@Suite("Settings and formatting")
@MainActor
struct SettingsTests {
    @Test func buildsBridgeURLsFromConfigurableIdentifiers() {
        let defaults = UserDefaults(suiteName: "BandLevelsTests-\(UUID().uuidString)")!
        let settings = AppSettings(defaults: defaults, bundle: Bundle(for: BundleToken.self))
        settings.bridgeHost = "192.168.1.20"
        settings.bridgePort = 8123
        #expect(settings.streamURL?.absoluteString == "ws://192.168.1.20:8123/api/v1/stream")
        #expect(settings.periodsURL?.absoluteString == "http://192.168.1.20:8123/api/v1/periods")
        settings.streamPath = "stream"
        #expect(settings.connectionProblem != nil)
    }

    @Test func persistsEmphasisAndRefreshPeriod() {
        let suite = "BandLevelsTests-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        let first = AppSettings(defaults: defaults, bundle: Bundle(for: BundleToken.self))
        first.emphasis = .lufs
        first.displayRefreshMilliseconds = 250
        let second = AppSettings(defaults: defaults, bundle: Bundle(for: BundleToken.self))
        #expect(second.emphasis == .lufs)
        #expect(second.displayRefreshMilliseconds == 250)
    }

    @Test func formatsAndNormalizesMetrics() {
        #expect(MetricKind.gain.formatted(0.724) == "72%")
        #expect(MetricKind.vu.formatted(1.25).hasPrefix("+"))
        #expect(MetricKind.dbfs.formatted(nil) == "—")
        #expect(MetricKind.dbfs.normalized(-30) == 0.5)
        #expect(MetricKind.lufs.normalized(-200) == 0)
        #expect(MetricKind.gain.normalized(2) == 1)
    }
}

private final class BundleToken {}
