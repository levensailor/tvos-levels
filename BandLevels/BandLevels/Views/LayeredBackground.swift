import SwiftUI

/// Deepest plane: base gradient with soft accent glows. Moves at 0.3x scroll speed.
struct LayeredBackground: View {
    let palette: Theme.Palette

    var body: some View {
        ZStack {
            LinearGradient(colors: [palette.base, palette.baseDeep], startPoint: .top, endPoint: .bottom)
            GeometryReader { proxy in
                let size = proxy.size
                Circle()
                    .fill(palette.accentGlow)
                    .frame(width: size.width * 0.55)
                    .blur(radius: 160)
                    .position(x: size.width * 0.2, y: size.height * 0.15)
                Circle()
                    .fill(palette.accentGlow.opacity(0.6))
                    .frame(width: size.width * 0.45)
                    .blur(radius: 180)
                    .position(x: size.width * 0.85, y: size.height * 0.9)
            }
        }
        .scaleEffect(1.2)
        .accessibilityHidden(true)
    }
}
