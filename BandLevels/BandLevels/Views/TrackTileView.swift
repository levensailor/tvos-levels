import SwiftUI

/// One populated track box: name, emphasized metric with meter, and the other three metrics.
struct TrackTileView: View {
    let track: BridgeTrack
    let emphasis: MetricKind
    let palette: Theme.Palette

    @Environment(\.isFocused) private var isFocused

    static let minimumHeight: CGFloat = 300

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.x(1)) {
            HStack {
                Text(String(format: "%02d", track.slot))
                    .themeFont(16, .semibold)
                    .foregroundStyle(palette.mutedText)
                    .monospacedDigit()
                Spacer(minLength: 0)
                if track.stale {
                    Text("STALE")
                        .themeFont(14, .heavy)
                        .foregroundStyle(palette.warning)
                }
            }
            Text(track.name)
                .themeFont(24, .heavy)
                .foregroundStyle(palette.text)
                .lineLimit(1)
                .minimumScaleFactor(0.6)

            VStack(alignment: .leading, spacing: 2) {
                Text(emphasis.formatted(emphasis.value(in: track)))
                    .themeFont(40, .heavy)
                    .foregroundStyle(palette.accent)
                    .monospacedDigit()
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                Text(emphasis.unit)
                    .themeFont(14, .semibold)
                    .foregroundStyle(palette.mutedText)
            }
            MeterBar(fraction: emphasis.normalized(emphasis.value(in: track)), palette: palette)

            VStack(spacing: Theme.Spacing.x(0.5)) {
                ForEach(MetricKind.allCases.filter { $0 != emphasis }) { metric in
                    HStack {
                        Text(metric.title)
                            .themeFont(16, .semibold)
                            .foregroundStyle(palette.mutedText)
                        Spacer(minLength: Theme.Spacing.x(0.5))
                        Text(metric.formatted(metric.value(in: track)))
                            .themeFont(18, .regular)
                            .foregroundStyle(palette.text)
                            .monospacedDigit()
                    }
                }
            }
            .padding(.top, Theme.Spacing.x(0.5))
        }
        .padding(Theme.Spacing.x(2))
        .frame(maxWidth: .infinity, minHeight: Self.minimumHeight, alignment: .topLeading)
        .glassPlane(palette, level: isFocused ? 2 : 1, elevation: isFocused ? .lifted : .resting)
        .opacity(track.stale ? 0.6 : 1)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilitySummary)
    }

    private var accessibilitySummary: String {
        let values = MetricKind.allCases.map { "\($0.title) \($0.formatted($0.value(in: track)))" }
        return "\(track.name), " + values.joined(separator: ", ")
    }
}

struct EmptySlotView: View {
    let number: Int
    let palette: Theme.Palette

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: Theme.Radius.card, style: .continuous)
        VStack(alignment: .leading, spacing: Theme.Spacing.x(1)) {
            Text(String(format: "%02d", number))
                .themeFont(16, .semibold)
                .monospacedDigit()
            Spacer()
            Text("Available")
                .themeFont(20, .semibold)
            Text("Add a track in tracks.json")
                .themeFont(14, .regular)
        }
        .foregroundStyle(palette.emptySlot)
        .padding(Theme.Spacing.x(2))
        .frame(maxWidth: .infinity, minHeight: TrackTileView.minimumHeight, alignment: .topLeading)
        .background(shape.fill(palette.surface[0].opacity(0.35)))
        .overlay(shape.strokeBorder(palette.emptySlot, style: StrokeStyle(lineWidth: 2, dash: [8, 6])))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Slot \(number) available")
    }
}

struct MeterBar: View {
    let fraction: Double
    let palette: Theme.Palette

    var body: some View {
        GeometryReader { proxy in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(palette.text.opacity(0.08))
                Capsule()
                    .fill(LinearGradient(
                        colors: [palette.accent.opacity(0.65), palette.accent],
                        startPoint: .leading,
                        endPoint: .trailing
                    ))
                    .frame(width: max(0, proxy.size.width * fraction))
                    .shadow(color: palette.accentGlow, radius: 8)
            }
        }
        .frame(height: Theme.Spacing.x(1))
        .animation(.linear(duration: 0.1), value: fraction)
    }
}
