import SwiftUI

/// Dimensional Layering design tokens.
enum Theme {
    struct Palette {
        let base: Color
        let baseDeep: Color
        let surface: [Color]
        let text: Color
        let mutedText: Color
        let accent: Color
        let accentGlow: Color
        let borderOuter: Color
        let borderInner: Color
        let emptySlot: Color
        let warning: Color
        let shadow: Color

        static let dark = Palette(
            base: Color(hex: 0x0F172A),
            baseDeep: Color(hex: 0x020617),
            surface: [
                Color(hex: 0x1E293B, opacity: 0.55),
                Color(hex: 0x334155, opacity: 0.45),
                Color(hex: 0x475569, opacity: 0.40),
            ],
            text: Color(hex: 0xE2E8F0),
            mutedText: Color(hex: 0xE2E8F0, opacity: 0.62),
            accent: Color(hex: 0x38BDF8),
            accentGlow: Color(hex: 0x38BDF8, opacity: 0.45),
            borderOuter: Color(hex: 0xFFFFFF, opacity: 0.10),
            borderInner: Color(hex: 0x38BDF8, opacity: 0.22),
            emptySlot: Color(hex: 0xE2E8F0, opacity: 0.22),
            warning: Color(hex: 0xFBBF24),
            shadow: Color(hex: 0x000000)
        )

        static let light = Palette(
            base: Color(hex: 0xF1F5F9),
            baseDeep: Color(hex: 0xE2E8F0),
            surface: [
                Color(hex: 0xFFFFFF, opacity: 0.70),
                Color(hex: 0xFFFFFF, opacity: 0.80),
                Color(hex: 0xFFFFFF, opacity: 0.90),
            ],
            text: Color(hex: 0x0F172A),
            mutedText: Color(hex: 0x0F172A, opacity: 0.62),
            accent: Color(hex: 0x0284C7),
            accentGlow: Color(hex: 0x0EA5E9, opacity: 0.35),
            borderOuter: Color(hex: 0x0F172A, opacity: 0.10),
            borderInner: Color(hex: 0x0284C7, opacity: 0.20),
            emptySlot: Color(hex: 0x0F172A, opacity: 0.22),
            warning: Color(hex: 0xB45309),
            shadow: Color(hex: 0x0F172A)
        )

        static func resolve(_ scheme: ColorScheme) -> Palette {
            scheme == .dark ? dark : light
        }
    }

    /// 8-point spacing scale.
    enum Spacing {
        static let unit: CGFloat = 8
        static func x(_ multiple: CGFloat) -> CGFloat { unit * multiple }
    }

    enum Radius {
        static let card: CGFloat = 16
        static let meter: CGFloat = 4
    }

    /// Plane overlap between layered surfaces (16–32 pt).
    enum Overlap {
        static let minimum: CGFloat = 16
        static let header: CGFloat = 24
        static let maximum: CGFloat = 32
    }

    enum Glass {
        static let saturation: Double = 1.8
        static let tintOpacity: Double = 1.0
    }

    enum Motion {
        static let liftDuration: Double = 0.25
        /// cubic-bezier(0.4, 0, 0.2, 1) over 250 ms
        static var lift: Animation { .timingCurve(0.4, 0, 0.2, 1, duration: liftDuration) }
        static let liftOffset: CGFloat = -8
        static let liftScale: CGFloat = 1.04
        static let backgroundParallax: CGFloat = 0.3
        static let cardParallax: CGFloat = 1.0
    }

    /// Progressive shadows: each elevation adds a wider, softer layer.
    enum Elevation: Int, CaseIterable {
        case resting = 1
        case raised = 2
        case lifted = 3

        struct Layer {
            let opacity: Double
            let radius: CGFloat
            let y: CGFloat
        }

        static let ramp: [Layer] = [
            Layer(opacity: 0.10, radius: 2, y: 1),
            Layer(opacity: 0.14, radius: 8, y: 4),
            Layer(opacity: 0.18, radius: 24, y: 12),
        ]

        var layers: [Layer] { Array(Self.ramp.prefix(rawValue)) }
    }

    enum Typography {
        struct Family {
            let name: String
            let resource: String
            let fileExtension: String
        }

        /// Satoshi, then Inter, then the system font.
        static let families = [
            Family(name: "Satoshi", resource: "Satoshi-Variable", fileExtension: "ttf"),
            Family(name: "Inter", resource: "InterVariable", fileExtension: "ttf"),
        ]

        enum Weight: Int, Sendable {
            case regular = 400
            case semibold = 600
            case heavy = 800

            var system: Font.Weight {
                switch self {
                case .regular: .regular
                case .semibold: .semibold
                case .heavy: .heavy
                }
            }
        }
    }
}

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity
        )
    }
}

extension View {
    /// Layered glass surface: material blur, saturation boost, tinted plane, and dual borders.
    func glassPlane(_ palette: Theme.Palette, level: Int, elevation: Theme.Elevation) -> some View {
        let shape = RoundedRectangle(cornerRadius: Theme.Radius.card, style: .continuous)
        let tint = palette.surface[min(max(level, 0), palette.surface.count - 1)]
        return self
            .background {
                shape
                    .fill(.ultraThinMaterial)
                    .saturation(Theme.Glass.saturation)
                    .overlay(shape.fill(tint.opacity(Theme.Glass.tintOpacity)))
            }
            .overlay {
                shape.strokeBorder(palette.borderOuter, lineWidth: 1)
                    .overlay(shape.inset(by: 1).strokeBorder(palette.borderInner, lineWidth: 1))
            }
            .progressiveShadow(palette, elevation: elevation)
    }

    func progressiveShadow(_ palette: Theme.Palette, elevation: Theme.Elevation) -> some View {
        let layers = Theme.Elevation.ramp
        let count = elevation.rawValue
        return self
            .shadow(color: palette.shadow.opacity(count >= 1 ? layers[0].opacity : 0), radius: layers[0].radius, y: layers[0].y)
            .shadow(color: palette.shadow.opacity(count >= 2 ? layers[1].opacity : 0), radius: layers[1].radius, y: layers[1].y)
            .shadow(color: palette.shadow.opacity(count >= 3 ? layers[2].opacity : 0), radius: layers[2].radius, y: layers[2].y)
    }
}
