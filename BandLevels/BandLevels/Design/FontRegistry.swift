import CoreText
import SwiftUI

/// Loads the first available bundled variable font (Satoshi, then Inter) and
/// instantiates exact 400/600/800 weights through the `wght` variation axis.
@MainActor
final class FontRegistry {
    static let shared = FontRegistry()

    /// OpenType tag 'wght'.
    private static let weightAxisTag = 0x7767_6874

    private struct Key: Hashable {
        let size: CGFloat
        let weight: Theme.Typography.Weight
    }

    private(set) var activeFamily: String?
    private var descriptor: CTFontDescriptor?
    private var cache: [Key: Font] = [:]

    func load(bundle: Bundle = .main) {
        for family in Theme.Typography.families {
            guard let url = bundle.url(forResource: family.resource, withExtension: family.fileExtension),
                  let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as? [CTFontDescriptor],
                  let first = descriptors.first
            else { continue }
            descriptor = first
            activeFamily = family.name
            cache.removeAll()
            AppLog.info(AppLog.ui, "Using bundled font \(family.name)")
            return
        }
        AppLog.info(AppLog.ui, "No bundled font found; using the system font")
    }

    func font(size: CGFloat, weight: Theme.Typography.Weight) -> Font {
        let key = Key(size: size, weight: weight)
        if let cached = cache[key] { return cached }
        let font: Font
        if let descriptor {
            let variation: [NSNumber: NSNumber] = [
                NSNumber(value: Self.weightAxisTag): NSNumber(value: weight.rawValue),
            ]
            let attributes = [kCTFontVariationAttribute as String: variation] as CFDictionary
            let weighted = CTFontDescriptorCreateCopyWithAttributes(descriptor, attributes)
            font = Font(CTFontCreateWithFontDescriptor(weighted, size, nil))
        } else {
            font = .system(size: size, weight: weight.system)
        }
        cache[key] = font
        return font
    }
}

extension View {
    @MainActor
    func themeFont(_ size: CGFloat, _ weight: Theme.Typography.Weight) -> some View {
        font(FontRegistry.shared.font(size: size, weight: weight))
    }
}
