import SwiftUI

/// Resona pastel "cottagecore" theme — palette + typography + reusable
/// surfaces. Pulled from the May 2026 brand mockups (sun mascot, mushroom
/// garden). Keep additions small: every new token here gets used by ≥2
/// views or it doesn't earn its keep.
enum Resona {

    // MARK: Palette — pastel washes from the brand sheet.

    enum Palette {
        // Backgrounds — design-system bg/card/border
        static let cream      = Color(hex: 0xFDF8F2) // page bg
        static let parchment  = Color(hex: 0xFFFFFF) // card bg
        static let mist       = Color(hex: 0xF5F0E8) // soft surface
        static let stone      = Color(hex: 0xE5E0D8) // dividers
        static let border     = Color(hex: 0xEDE8DF)

        // Brand — design-system swatches (#c4b5f4 etc.)
        static let lavender   = Color(hex: 0xC4B5F4)
        static let coral      = Color(hex: 0xF4846A)
        static let apricot    = Color(hex: 0xF9B98A)
        static let butter     = Color(hex: 0xF9E07A)
        static let sky        = Color(hex: 0x93C5FD)
        static let mint       = Color(hex: 0x6EE7B7)
        static let teal       = Color(hex: 0x2DD4BF)

        // Aliases (kept so existing call sites compile)
        static let peach      = apricot
        static let lilac      = Color(hex: 0xE0D4F8)
        static let blush      = Color(hex: 0xFCE7F3)

        // Ink — much darker than before for legibility
        static let ink        = Color(hex: 0x1E1B2E) // headings (near-black)
        static let inkSoft    = Color(hex: 0x4A4257) // body
        static let inkFaint   = Color(hex: 0x6B6260) // captions / muted

        // Verdict tints
        static let focus      = Color(hex: 0x4A7C59) // confirmed-focus green
        static let drift      = lavender
        static let alert      = coral
    }

    // MARK: Gradients

    enum Gradients {
        static let appBackground = LinearGradient(
            colors: [Palette.cream, Palette.lilac.opacity(0.35), Palette.sky.opacity(0.25)],
            startPoint: .topLeading, endPoint: .bottomTrailing
        )

        static let hero = LinearGradient(
            colors: [Palette.lilac.opacity(0.55), Palette.peach.opacity(0.45), Palette.sky.opacity(0.35)],
            startPoint: .topLeading, endPoint: .bottomTrailing
        )

        static let card = LinearGradient(
            colors: [Palette.parchment, Palette.cream],
            startPoint: .top, endPoint: .bottom
        )
    }

    // MARK: Typography — serif italic display + sans body, per brand sheet.

    enum Typography {
        // Design-system scale. Playfair Display isn't bundled — fall back
        // to system serif for `.serif` weight, which matches the brand
        // intent (display = elegant serif) on macOS via New York.
        //
        // Display 1: 56/64 — used sparingly (huge wordmark, splash)
        // Display 2: 40/48 — hero headlines ("Mind settling into focus")
        // Heading 1: 28/36 semibold serif — section titles
        // Heading 2: 20/28 semibold sans — card headers
        // Body 1:    16/24 — primary copy
        // Body 2:    14/20 — secondary copy
        // Label:     12/16 medium — eyebrow / chips
        // Caption:   11/16 — fine print
        static let display1 = Font.system(size: 56, weight: .bold, design: .serif)
        static let display2 = Font.system(size: 40, weight: .bold, design: .serif)
        static let display  = display2
        static let title    = Font.system(size: 28, weight: .semibold, design: .serif)
        static let heading1 = title
        static let heading2 = Font.system(size: 20, weight: .semibold, design: .default)
        static let headline = heading2
        static let body     = Font.system(size: 16, weight: .regular, design: .default)
        static let body2    = Font.system(size: 14, weight: .regular, design: .default)
        static let label    = Font.system(size: 12, weight: .medium, design: .default)
        static let caption  = Font.system(size: 12, weight: .regular, design: .default)
        static let pill     = Font.system(size: 14, weight: .medium, design: .default)

        /// Eyebrow text — uppercase tracked label above hero titles.
        static let eyebrow  = Font.system(size: 11, weight: .semibold, design: .default)
    }
}

// MARK: hex Color helper

extension Color {
    init(hex: UInt32, alpha: Double = 1) {
        let r = Double((hex >> 16) & 0xFF) / 255.0
        let g = Double((hex >> 8)  & 0xFF) / 255.0
        let b = Double( hex        & 0xFF) / 255.0
        self.init(.sRGB, red: r, green: g, blue: b, opacity: alpha)
    }
}

// MARK: View modifiers

/// Soft pastel card — used for verdict, metric, and content tiles.
struct ResonaCard: ViewModifier {
    var tint: Color = Resona.Palette.parchment
    var corner: CGFloat = 18

    func body(content: Content) -> some View {
        content
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: corner, style: .continuous)
                    .fill(tint)
            )
            .overlay(
                RoundedRectangle(cornerRadius: corner, style: .continuous)
                    .strokeBorder(Color.white.opacity(0.7), lineWidth: 1)
            )
            .shadow(color: Resona.Palette.lavender.opacity(0.18), radius: 12, x: 0, y: 6)
    }
}

extension View {
    func resonaCard(tint: Color = Resona.Palette.parchment, corner: CGFloat = 18) -> some View {
        modifier(ResonaCard(tint: tint, corner: corner))
    }
}

/// Pastel pill — used for nav tabs and chips.
struct ResonaPill: ViewModifier {
    var active: Bool = false
    var tint: Color = Resona.Palette.lavender

    func body(content: Content) -> some View {
        content
            .font(Resona.Typography.pill)
            .foregroundStyle(active ? Resona.Palette.ink : Resona.Palette.inkSoft)
            .padding(.horizontal, 14).padding(.vertical, 7)
            .background(
                Capsule().fill(active ? tint.opacity(0.55) : Color.white.opacity(0.6))
            )
            .overlay(
                Capsule().strokeBorder(active ? tint : Color.white.opacity(0.8), lineWidth: 1)
            )
    }
}

extension View {
    func resonaPill(active: Bool = false, tint: Color = Resona.Palette.lavender) -> some View {
        modifier(ResonaPill(active: active, tint: tint))
    }
}

// MARK: Asset access — load PNGs cropped from the brand mockups.

import AppKit

extension Image {
    /// Loads a PNG from the package bundle. Falls back to an SF Symbol if
    /// the asset is missing so swift build never breaks on a typo.
    static func resonaAsset(_ name: String, fallback: String = "sparkles") -> Image {
        if let url = Bundle.module.url(forResource: name, withExtension: "png"),
           let img = NSImage(contentsOf: url) {
            return Image(nsImage: img)
        }
        return Image(systemName: fallback)
    }
}
