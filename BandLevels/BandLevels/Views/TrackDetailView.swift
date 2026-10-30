import SwiftUI

/// Full-screen readout of all four metrics for one track.
struct TrackDetailView: View {
    let track: BridgeTrack
    let palette: Theme.Palette

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.x(4)) {
            Text(track.name)
                .themeFont(64, .heavy)
                .foregroundStyle(palette.text)
            HStack(spacing: Theme.Spacing.x(3)) {
                ForEach(MetricKind.allCases) { metric in
                    VStack(alignment: .leading, spacing: Theme.Spacing.x(1)) {
                        Text(metric.title)
                            .themeFont(24, .semibold)
                            .foregroundStyle(palette.mutedText)
                        Text(metric.formatted(metric.value(in: track)))
                            .themeFont(56, .heavy)
                            .foregroundStyle(palette.accent)
                            .monospacedDigit()
                        Text(metric.unit)
                            .themeFont(18, .regular)
                            .foregroundStyle(palette.mutedText)
                        MeterBar(fraction: metric.normalized(metric.value(in: track)), palette: palette)
                    }
                    .padding(Theme.Spacing.x(3))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .glassPlane(palette, level: 1, elevation: .raised)
                }
            }
            Text(track.updatedAt.map { "Updated \($0)" } ?? "No measurements yet")
                .themeFont(18, .regular)
                .foregroundStyle(track.stale ? palette.warning : palette.mutedText)
        }
        .padding(Theme.Spacing.x(8))
    }
}
