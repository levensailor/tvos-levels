import SwiftUI

private let dashboardScrollSpace = "dashboardScroll"

/// Public monitoring dashboard: a header plane overlapping a 2 x 8 grid plane of track boxes.
struct DashboardView: View {
    let model: DashboardModel
    @Bindable var settings: AppSettings

    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var scrollOffset: CGFloat = 0
    @State private var showingSettings = false
    @State private var selectedSlot: DashboardSlot?

    var body: some View {
        let palette = Theme.Palette.resolve(colorScheme)
        ZStack {
            LayeredBackground(palette: palette)
                .offset(y: reduceMotion ? 0 : scrollOffset * Theme.Motion.backgroundParallax)
                .ignoresSafeArea()

            ScrollView(.vertical) {
                VStack(alignment: .leading, spacing: 0) {
                    header(palette)
                        .zIndex(1)
                    grid(palette)
                        .padding(.top, -Theme.Overlap.header)
                        .zIndex(0)
                }
                .onGeometryChange(for: CGFloat.self) { proxy in
                    proxy.frame(in: .named(dashboardScrollSpace)).minY
                } action: { newValue in
                    scrollOffset = newValue
                }
            }
            .coordinateSpace(.named(dashboardScrollSpace))
            .scrollClipDisabled()
        }
        .sheet(isPresented: $showingSettings) {
            SettingsView(model: model, settings: settings)
        }
        .sheet(item: $selectedSlot) { slot in
            if let track = slot.track {
                TrackDetailView(track: track, palette: palette)
            }
        }
    }

    private func header(_ palette: Theme.Palette) -> some View {
        HStack(alignment: .center, spacing: Theme.Spacing.x(3)) {
            VStack(alignment: .leading, spacing: Theme.Spacing.x(0.5)) {
                Text("Band Levels")
                    .themeFont(44, .heavy)
                    .foregroundStyle(palette.text)
                HStack(spacing: Theme.Spacing.x(1.5)) {
                    Circle()
                        .fill(model.connection.isLive ? palette.accent : palette.warning)
                        .frame(width: 12, height: 12)
                        .shadow(color: model.connection.isLive ? palette.accentGlow : .clear, radius: 6)
                    Text(model.connection.label)
                        .lineLimit(1)
                    Text("·")
                    Text("\(model.populatedCount) of \(BridgeContract.slotCount) slots")
                    if let sequence = model.sequence {
                        Text("· seq \(sequence)")
                            .monospacedDigit()
                    }
                }
                .themeFont(18, .semibold)
                .foregroundStyle(palette.mutedText)
                if let rejection = model.lastRejection {
                    Text("Rejected payload: \(rejection)")
                        .themeFont(16, .regular)
                        .foregroundStyle(palette.warning)
                        .lineLimit(1)
                }
            }
            Spacer(minLength: Theme.Spacing.x(2))
            Picker("Emphasis", selection: $settings.emphasis) {
                ForEach(MetricKind.allCases) { metric in
                    Text(metric.title).tag(metric)
                }
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 560)
            Button {
                showingSettings = true
            } label: {
                Label("Settings", systemImage: "gearshape")
            }
        }
        .padding(Theme.Spacing.x(3))
        .glassPlane(palette, level: 1, elevation: .raised)
        .padding(.horizontal, Theme.Spacing.x(4))
    }

    private func grid(_ palette: Theme.Palette) -> some View {
        VStack(spacing: Theme.Spacing.x(2)) {
            ForEach(Array(model.rows.enumerated()), id: \.offset) { _, row in
                HStack(alignment: .top, spacing: Theme.Spacing.x(2)) {
                    ForEach(row) { slot in
                        tile(for: slot, palette: palette)
                    }
                }
            }
        }
        .padding(.horizontal, Theme.Spacing.x(3))
        .padding(.bottom, Theme.Spacing.x(3))
        .padding(.top, Theme.Overlap.header + Theme.Spacing.x(3))
        .glassPlane(palette, level: 0, elevation: .resting)
    }

    @ViewBuilder
    private func tile(for slot: DashboardSlot, palette: Theme.Palette) -> some View {
        if let track = slot.track {
            Button {
                selectedSlot = slot
            } label: {
                TrackTileView(track: track, emphasis: settings.emphasis, palette: palette)
            }
            .buttonStyle(TileButtonStyle())
        } else {
            EmptySlotView(number: slot.number, palette: palette)
        }
    }
}

/// Focus lift: 250 ms cubic-bezier rise with scale, replacing the tvOS default card effect.
struct TileButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        TileButtonBody(configuration: configuration)
    }

    private struct TileButtonBody: View {
        let configuration: ButtonStyleConfiguration
        @Environment(\.isFocused) private var isFocused

        var body: some View {
            configuration.label
                .scaleEffect(isFocused ? Theme.Motion.liftScale : (configuration.isPressed ? 0.98 : 1))
                .offset(y: isFocused ? Theme.Motion.liftOffset : 0)
                .zIndex(isFocused ? 1 : 0)
                .animation(Theme.Motion.lift, value: isFocused)
                .animation(Theme.Motion.lift, value: configuration.isPressed)
        }
    }
}
