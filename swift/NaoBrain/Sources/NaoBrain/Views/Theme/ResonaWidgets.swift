import SwiftUI

// MARK: FocusOrb — Resona brand mascot, drawn entirely in SwiftUI.
//
// Faithful port of the design-system hero orb (resona_design_system.html)
// plus a few extras: multi-layer iridescent halo, glossy sheen, breathing
// scale + halo pulse, sparkle constellation, soft lavender ribbon swoop.
// The face is a faded shy smile so the orb stays gentle at hero scale.
//
// Tuned for ~180–220 pt — values scale with `s` so it stays sharp at any
// size we render at.

struct FocusOrb: View {
    /// Mascot mood. Drives both the face geometry and which scene/asset
    /// renders behind it.
    /// - content : default smiling orb (focused, calm, ok states)
    /// - alert   : wide eyes (alert / very noisy signal)
    /// - sleepy  : moon-cloud — used when Quiet ON / agents paused
    /// - settling: violet jelly — used when warming-up / calibrating
    enum Mood { case content, alert, sleepy, settling }
    var mood: Mood = .content

    /// `embedded = true` drops the scene backdrop (sky/meadow/clouds) so
    /// the orb floats on whatever surface it's placed in. Used inside the
    /// hero card where the parent already supplies a pastel gradient.
    /// `embedded = false` is the standalone scene (used in widgets / app
    /// icon contexts).
    var embedded: Bool = true

    /// 0…1 focus signal that drives pulse speed + amplitude. Low values
    /// = slow gentle breath; high values = faster, livelier pulse. Pass
    /// `nil` to use a steady neutral cadence.
    var focusLevel: Double? = nil

    /// Animate breathing + halo pulse. Disable for static thumbnails.
    var animated: Bool = true

    @State private var breathe: Bool = false

    /// Pulse duration in seconds — derived from focusLevel.
    private var pulseDuration: Double {
        guard let f = focusLevel else { return 3.6 }
        // 4.6 s at f=0 → 1.8 s at f=1.0
        return 4.6 - (max(0, min(1, f)) * 2.8)
    }

    /// Pulse amplitude — derived from focusLevel.
    private var pulseScale: CGFloat {
        guard let f = focusLevel else { return 1.03 }
        return 1.02 + CGFloat(max(0, min(1, f))) * 0.05
    }

    var body: some View {
        GeometryReader { geo in
            let s = min(geo.size.width, geo.size.height)
            ZStack {
                if !embedded {
                    skyWash(s: s)
                    meadow(s: s)
                    cloudPair(s: s)
                }
                // Orb scene swaps with mood — sleepy/settling render their
                // own bespoke composition, content/alert use the iridescent
                // orb body.
                switch mood {
                case .content, .alert:
                    halo(s: s)
                    ribbon(s: s)
                    orbBody(s: s)
                        .scaleEffect(breathe ? pulseScale : 1.0)
                    face(s: s)
                        .scaleEffect(breathe ? pulseScale : 1.0)
                case .sleepy:
                    halo(s: s).opacity(0.5)
                    sleepyMoonCloud(s: s)
                        .scaleEffect(breathe ? 1.02 : 1.0)
                case .settling:
                    halo(s: s).opacity(0.4)
                    settlingJelly(s: s)
                        .scaleEffect(breathe ? 1.025 : 1.0)
                }
                sparkles(s: s)
            }
            .frame(width: s, height: s)
            .clipShape(
                RoundedRectangle(cornerRadius: embedded ? 0 : s * 0.10, style: .continuous)
            )
            .onAppear {
                guard animated else { return }
                withAnimation(.easeInOut(duration: pulseDuration).repeatForever(autoreverses: true)) {
                    breathe = true
                }
            }
            .onChange(of: pulseDuration) { _, new in
                guard animated else { return }
                breathe = false
                withAnimation(.easeInOut(duration: new).repeatForever(autoreverses: true)) {
                    breathe = true
                }
            }
        }
        .aspectRatio(1, contentMode: .fit)
    }

    // MARK: alternate-mood scenes

    /// Sleepy moon-cloud — three overlapping puff-circles in sky-blue
    /// gradient with closed sleeping eyes + Z. Mirrors the
    /// sleepy_moon_cloud.svg silhouette.
    private func sleepyMoonCloud(s: CGFloat) -> some View {
        let cloudGrad = LinearGradient(
            colors: [Color(hex: 0xBAE6FD), Color(hex: 0x7DD3FC)],
            startPoint: .top, endPoint: .bottom
        )
        let ink = Color(hex: 0x2A1F45)
        return ZStack {
            // Cloud body — three overlapping circles
            ZStack {
                Circle().fill(cloudGrad)
                    .frame(width: s * 0.30, height: s * 0.30)
                    .offset(x: -s * 0.13, y: s * 0.02)
                Circle().fill(cloudGrad)
                    .frame(width: s * 0.40, height: s * 0.40)
                    .offset(y: -s * 0.04)
                Circle().fill(cloudGrad)
                    .frame(width: s * 0.28, height: s * 0.28)
                    .offset(x: s * 0.14, y: s * 0.03)
            }
            .shadow(color: Color(hex: 0xC4B5F4).opacity(0.55), radius: 14, x: 0, y: 8)

            // Sleeping eyes (~~)
            HStack(spacing: s * 0.07) {
                SleepArc().stroke(ink.opacity(0.85),
                                  style: StrokeStyle(lineWidth: 2.6, lineCap: .round))
                    .frame(width: s * 0.06, height: s * 0.025)
                SleepArc().stroke(ink.opacity(0.85),
                                  style: StrokeStyle(lineWidth: 2.6, lineCap: .round))
                    .frame(width: s * 0.06, height: s * 0.025)
            }
            .offset(y: -s * 0.005)

            // Tiny smile
            OrbSmile()
                .stroke(ink.opacity(0.75),
                        style: StrokeStyle(lineWidth: 2.0, lineCap: .round))
                .frame(width: s * 0.07, height: s * 0.030)
                .offset(y: s * 0.04)

            // "z" floating up
            Text("z")
                .font(.system(size: s * 0.10, weight: .bold, design: .serif))
                .italic()
                .foregroundStyle(Color(hex: 0xC4B5F4))
                .offset(x: s * 0.20, y: -s * 0.18)
        }
    }

    /// Settling jelly — purple translucent blob inside a glass dome,
    /// matching settling_jelly_terrarium.svg's silhouette.
    private func settlingJelly(s: CGFloat) -> some View {
        let jellyGrad = LinearGradient(
            colors: [Color(hex: 0xC4B5F4), Color(hex: 0xA78BFA)],
            startPoint: .top, endPoint: .bottom
        )
        let domeGrad = LinearGradient(
            colors: [Color.white.opacity(0.55), Color.white.opacity(0.10)],
            startPoint: .topLeading, endPoint: .bottomTrailing
        )
        let ink = Color(hex: 0x2A1F45)
        return ZStack {
            // Glass dome arc
            DomeShape()
                .stroke(domeGrad, lineWidth: 2)
                .frame(width: s * 0.46, height: s * 0.50)
                .offset(y: -s * 0.02)
            // Dome highlight
            DomeShape()
                .fill(domeGrad)
                .frame(width: s * 0.46, height: s * 0.50)
                .opacity(0.25)
                .offset(y: -s * 0.02)
            // Jelly body
            Ellipse()
                .fill(jellyGrad)
                .frame(width: s * 0.26, height: s * 0.28)
                .offset(y: s * 0.04)
                .shadow(color: Color(hex: 0x7C5FE6).opacity(0.4), radius: 10, x: 0, y: 4)
            // Eyes
            HStack(spacing: s * 0.06) {
                Circle().fill(ink.opacity(0.85)).frame(width: s * 0.025, height: s * 0.025)
                Circle().fill(ink.opacity(0.85)).frame(width: s * 0.025, height: s * 0.025)
            }
            .offset(y: s * 0.025)
            // Smile
            OrbSmile()
                .stroke(ink.opacity(0.70),
                        style: StrokeStyle(lineWidth: 1.8, lineCap: .round))
                .frame(width: s * 0.06, height: s * 0.025)
                .offset(y: s * 0.06)
        }
    }

    // MARK: scene background — soft gradient sky behind the orb

    private func skyWash(s: CGFloat) -> some View {
        LinearGradient(
            colors: [
                Color(hex: 0xE0F2FE),  // sky blue top
                Color(hex: 0xF3E8FF),  // lavender wash mid
                Color(hex: 0xFFE4E1)   // peach cream bottom
            ],
            startPoint: .top, endPoint: .bottom
        )
    }

    /// Soft pastel meadow plate under the orb — gives the mascot a place
    /// to stand instead of floating in void.
    private func meadow(s: CGFloat) -> some View {
        ZStack {
            // Ground crescent
            Ellipse()
                .fill(
                    LinearGradient(
                        colors: [
                            Color(hex: 0xD9F99D).opacity(0.45),
                            Color(hex: 0x86EFAC).opacity(0.35)
                        ],
                        startPoint: .top, endPoint: .bottom
                    )
                )
                .frame(width: s * 0.78, height: s * 0.18)
                .offset(y: s * 0.30)
                .blur(radius: 1.5)

            // Tiny flowers on the plate
            ForEach(Array(stride(from: -0.30, through: 0.30, by: 0.12)), id: \.self) { x in
                Circle()
                    .fill(flowerColor(x))
                    .frame(width: s * 0.024, height: s * 0.024)
                    .offset(x: x * s, y: s * 0.31)
            }
        }
    }

    /// Two soft cloud puffs above the orb for atmosphere.
    private func cloudPair(s: CGFloat) -> some View {
        ZStack {
            cloudPuff(s: s).offset(x: -s * 0.32, y: -s * 0.30).opacity(0.75)
            cloudPuff(s: s).offset(x:  s * 0.30, y: -s * 0.36).opacity(0.6).scaleEffect(0.75)
        }
    }

    /// Deterministic color picker for flower stickers — keyed by x offset
    /// so the row stays stable across renders.
    private func flowerColor(_ x: Double) -> Color {
        let palette = [
            Resona.Palette.coral,
            Resona.Palette.lavender,
            Resona.Palette.butter,
            Resona.Palette.sky,
            Resona.Palette.mint
        ]
        let idx = abs(Int((x + 1.0) * 100)) % palette.count
        return palette[idx]
    }

    private func cloudPuff(s: CGFloat) -> some View {
        ZStack {
            Circle().frame(width: s * 0.10, height: s * 0.10).offset(x: -s * 0.04)
            Circle().frame(width: s * 0.13, height: s * 0.13)
            Circle().frame(width: s * 0.10, height: s * 0.10).offset(x:  s * 0.05)
        }
        .foregroundStyle(Color.white.opacity(0.85))
        .shadow(color: Resona.Palette.lavender.opacity(0.20), radius: 4)
    }

    // MARK: layers

    /// Three concentric haloes at decreasing radius + opacity, sharing the
    /// iridescent radial gradient. Matches the SVG's three nested circles.
    private func halo(s: CGFloat) -> some View {
        let stops: [Gradient.Stop] = [
            Gradient.Stop(color: Color(hex: 0xFDE68A).opacity(0.9), location: 0),
            Gradient.Stop(color: Color(hex: 0xF9A8D4).opacity(0.8), location: 0.40),
            Gradient.Stop(color: Color(hex: 0xA5B4FC).opacity(0.7), location: 0.80),
            Gradient.Stop(color: Color(hex: 0x6EE7B7).opacity(0.5), location: 1.0),
        ]
        let grad = RadialGradient(
            gradient: Gradient(stops: stops),
            center: UnitPoint(x: 0.40, y: 0.35),
            startRadius: s * 0.05,
            endRadius: s * 0.50
        )
        return ZStack {
            Circle().fill(grad).opacity(0.30)
            Circle().fill(grad).opacity(0.40).frame(width: s * 0.80, height: s * 0.80)
        }
        .blur(radius: s * 0.015)
    }

    /// Body of the orb — one ellipse w/ the iridescent gradient + a soft
    /// drop shadow. Slightly taller than wide for that egg-like kawaii
    /// silhouette in the design system.
    private func orbBody(s: CGFloat) -> some View {
        let stops: [Gradient.Stop] = [
            Gradient.Stop(color: Color(hex: 0xFDE68A).opacity(0.95), location: 0),
            Gradient.Stop(color: Color(hex: 0xF9A8D4).opacity(0.95), location: 0.45),
            Gradient.Stop(color: Color(hex: 0xA5B4FC).opacity(0.95), location: 0.85),
            Gradient.Stop(color: Color(hex: 0x6EE7B7).opacity(0.85), location: 1.0),
        ]
        let grad = RadialGradient(
            gradient: Gradient(stops: stops),
            center: UnitPoint(x: 0.40, y: 0.35),
            startRadius: s * 0.02,
            endRadius: s * 0.36
        )
        return ZStack {
            // Body — bigger and more saturated than v1
            Ellipse()
                .fill(grad)
                .frame(width: s * 0.50, height: s * 0.52)
                .shadow(color: Color(hex: 0xC4B5F4).opacity(0.55), radius: 18, x: 0, y: 8)
                .shadow(color: Color(hex: 0xF9A8D4).opacity(0.35), radius: 6, x: 0, y: 2)
            // Glossy sheen — top-left highlight
            Ellipse()
                .fill(
                    LinearGradient(
                        colors: [Color.white.opacity(0.85), Color.white.opacity(0)],
                        startPoint: .topLeading, endPoint: .center
                    )
                )
                .frame(width: s * 0.24, height: s * 0.16)
                .offset(x: -s * 0.07, y: -s * 0.10)
            // Tiny pin-point starburst — adds the "alive" feel
            Image(systemName: "sparkle")
                .font(.system(size: s * 0.05, weight: .semibold))
                .foregroundStyle(.white.opacity(0.85))
                .offset(x: -s * 0.03, y: -s * 0.13)
            // Rim light — keeps the silhouette readable
            Ellipse()
                .strokeBorder(Color.white.opacity(0.65), lineWidth: 1.4)
                .frame(width: s * 0.50, height: s * 0.52)
        }
    }

    /// Face — eyes + soft smile + cheek blushes. Stronger ink than v1
    /// because at hero scale the face needs to read at-a-glance.
    private func face(s: CGFloat) -> some View {
        let ink = Color(hex: 0x2A1F45) // slightly darker than palette ink for contrast on bright orb
        return ZStack {
            // Eyes
            Group {
                if mood == .content {
                    HStack(spacing: s * 0.085) {
                        OrbEye().stroke(ink.opacity(0.85),
                                        style: StrokeStyle(lineWidth: 2.8, lineCap: .round))
                            .frame(width: s * 0.070, height: s * 0.040)
                        OrbEye().stroke(ink.opacity(0.85),
                                        style: StrokeStyle(lineWidth: 2.8, lineCap: .round))
                            .frame(width: s * 0.070, height: s * 0.040)
                    }
                    .offset(y: -s * 0.022)
                } else {
                    HStack(spacing: s * 0.085) {
                        Circle().fill(ink.opacity(0.90)).frame(width: s * 0.040, height: s * 0.040)
                        Circle().fill(ink.opacity(0.90)).frame(width: s * 0.040, height: s * 0.040)
                    }
                    .offset(y: -s * 0.022)
                }
            }

            // Smile — proper U curve, more visible
            OrbSmile()
                .stroke(ink.opacity(0.80),
                        style: StrokeStyle(lineWidth: 2.4, lineCap: .round))
                .frame(width: s * 0.11, height: s * 0.05)
                .offset(y: s * 0.045)

            // Cheek blushes
            HStack(spacing: s * 0.26) {
                Circle()
                    .fill(
                        RadialGradient(
                            gradient: Gradient(colors: [
                                Color(hex: 0xFCA5A5).opacity(0.7),
                                Color(hex: 0xFCA5A5).opacity(0.0)
                            ]),
                            center: .center,
                            startRadius: 0,
                            endRadius: s * 0.04
                        )
                    )
                    .frame(width: s * 0.075, height: s * 0.075)
                Circle()
                    .fill(
                        RadialGradient(
                            gradient: Gradient(colors: [
                                Color(hex: 0xFCA5A5).opacity(0.7),
                                Color(hex: 0xFCA5A5).opacity(0.0)
                            ]),
                            center: .center,
                            startRadius: 0,
                            endRadius: s * 0.04
                        )
                    )
                    .frame(width: s * 0.075, height: s * 0.075)
            }
            .offset(y: s * 0.025)
        }
    }

    /// Soft lavender→pink ribbon arc that swoops behind the orb. Matches
    /// the focus_orb_hero SVG's wave element.
    private func ribbon(s: CGFloat) -> some View {
        Ribbon()
            .stroke(
                LinearGradient(
                    colors: [
                        Color(hex: 0xC4B5F4).opacity(0.55),
                        Color(hex: 0xE0B8F8).opacity(0.85),
                        Color(hex: 0xF9A8D4).opacity(0.65),
                        Color.clear
                    ],
                    startPoint: .leading, endPoint: .trailing
                ),
                style: StrokeStyle(lineWidth: s * 0.045, lineCap: .round)
            )
            .frame(width: s * 0.92, height: s * 0.30)
            .offset(y: s * 0.10)
            .blur(radius: 0.5)
    }

    /// Constellation of star sparkles around the orb rim. Uses the SF
    /// "sparkle" symbol for clean rendering at small sizes.
    private func sparkles(s: CGFloat) -> some View {
        ZStack {
            sparkle(at: CGPoint(x:  0.18, y: -0.42), size: 0.06, color: Resona.Palette.lavender, base: s)
            sparkle(at: CGPoint(x:  0.40, y: -0.30), size: 0.04, color: Resona.Palette.butter, base: s)
            sparkle(at: CGPoint(x: -0.38, y: -0.22), size: 0.05, color: Resona.Palette.coral, base: s)
            sparkle(at: CGPoint(x: -0.42, y:  0.05), size: 0.035, color: Resona.Palette.lilac, base: s)
            sparkle(at: CGPoint(x:  0.42, y:  0.10), size: 0.045, color: Resona.Palette.lavender, base: s)
            sparkle(at: CGPoint(x: -0.20, y:  0.40), size: 0.035, color: Resona.Palette.mint, base: s)
            sparkle(at: CGPoint(x:  0.30, y:  0.42), size: 0.04, color: Resona.Palette.lavender, base: s)
        }
    }

    private func sparkle(at p: CGPoint, size: CGFloat, color: Color, base s: CGFloat) -> some View {
        Image(systemName: "sparkle")
            .font(.system(size: s * size, weight: .semibold))
            .foregroundStyle(color)
            .opacity(0.85)
            .offset(x: p.x * s, y: p.y * s)
    }
}

private struct OrbEye: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        // Upward smile-arc eye (closed / content)
        p.move(to: CGPoint(x: rect.minX, y: rect.maxY))
        p.addQuadCurve(
            to: CGPoint(x: rect.maxX, y: rect.maxY),
            control: CGPoint(x: rect.midX, y: rect.minY - rect.height * 0.4)
        )
        return p
    }
}

private struct OrbSmile: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: rect.minX, y: rect.minY))
        p.addQuadCurve(
            to: CGPoint(x: rect.maxX, y: rect.minY),
            control: CGPoint(x: rect.midX, y: rect.maxY * 1.7)
        )
        return p
    }
}

private struct SleepArc: Shape {
    /// Tiny `~` curve used as a closed sleeping eye.
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: rect.minX, y: rect.midY))
        p.addQuadCurve(
            to: CGPoint(x: rect.midX, y: rect.midY),
            control: CGPoint(x: rect.width * 0.25, y: rect.minY)
        )
        p.addQuadCurve(
            to: CGPoint(x: rect.maxX, y: rect.midY),
            control: CGPoint(x: rect.width * 0.75, y: rect.maxY)
        )
        return p
    }
}

private struct DomeShape: Shape {
    /// Rounded glass dome arc — used as the terrarium silhouette.
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: rect.minX, y: rect.maxY))
        p.addLine(to: CGPoint(x: rect.minX, y: rect.midY))
        p.addQuadCurve(
            to: CGPoint(x: rect.maxX, y: rect.midY),
            control: CGPoint(x: rect.midX, y: rect.minY)
        )
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
        return p
    }
}

private struct Ribbon: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        // S-curve ribbon: dips left, peaks middle, dips right.
        p.move(to: CGPoint(x: rect.minX, y: rect.midY))
        p.addCurve(
            to: CGPoint(x: rect.maxX, y: rect.midY),
            control1: CGPoint(x: rect.width * 0.30, y: rect.maxY * 1.4),
            control2: CGPoint(x: rect.width * 0.70, y: rect.minY - rect.height * 0.4)
        )
        return p
    }
}

// Backwards-compat alias — older call sites used `SunMascot`.
typealias SunMascot = FocusOrb
extension FocusOrb {
    init(content: Bool) {
        self.init(
            mood: content ? .content : .alert,
            embedded: true,
            focusLevel: nil,
            animated: true
        )
    }
}

// MARK: CoachOrb — tiny brand glyph for the Ask the Coach affordance.
//
// 22-pt iridescent dot with a single sparkle — reads as the mascot
// "speaking" without dragging the full hero scene into a list row.

struct CoachOrb: View {
    var size: CGFloat = 22
    var body: some View {
        let stops: [Gradient.Stop] = [
            Gradient.Stop(color: Color(hex: 0xFDE68A), location: 0),
            Gradient.Stop(color: Color(hex: 0xF9A8D4), location: 0.5),
            Gradient.Stop(color: Color(hex: 0xA5B4FC), location: 1.0),
        ]
        return ZStack {
            // Soft glow
            Circle()
                .fill(
                    RadialGradient(
                        gradient: Gradient(colors: [
                            Color(hex: 0xC4B5F4).opacity(0.55),
                            Color(hex: 0xC4B5F4).opacity(0.0)
                        ]),
                        center: .center,
                        startRadius: 0,
                        endRadius: size * 0.7
                    )
                )
                .frame(width: size * 1.6, height: size * 1.6)
            // Body
            Circle()
                .fill(
                    RadialGradient(
                        gradient: Gradient(stops: stops),
                        center: UnitPoint(x: 0.4, y: 0.35),
                        startRadius: 0,
                        endRadius: size * 0.6
                    )
                )
                .frame(width: size, height: size)
                .overlay(Circle().strokeBorder(Color.white.opacity(0.6), lineWidth: 1))
                .shadow(color: Color(hex: 0xF9A8D4).opacity(0.4), radius: 4, x: 0, y: 2)
            // Sparkle highlight
            Image(systemName: "sparkle")
                .font(.system(size: size * 0.35, weight: .semibold))
                .foregroundStyle(.white.opacity(0.85))
                .offset(x: -size * 0.18, y: -size * 0.18)
        }
        .frame(width: size * 1.6, height: size * 1.6)
    }
}

// MARK: DonutProgress — pastel ring chart.
//
// Filled fraction of `progress` (0...1). Stroke uses an angular gradient
// so the ring picks up multiple palette hues without looking like a
// generic ProgressView.

struct DonutProgress: View {
    var progress: Double         // 0...1
    var lineWidth: CGFloat = 14
    var label: String            // tiny caption above the value
    var valueText: String        // big middle text (e.g. "72%")
    var subtitle: String? = nil  // small under value
    var tint: [Color] = [
        Resona.Palette.peach,
        Resona.Palette.coral,
        Resona.Palette.lavender,
        Resona.Palette.peach
    ]

    var body: some View {
        VStack(spacing: 6) {
            Text(label)
                .font(Resona.Typography.caption)
                .foregroundStyle(Resona.Palette.inkSoft)

            ZStack {
                Circle()
                    .stroke(
                        Color.white.opacity(0.7),
                        style: StrokeStyle(lineWidth: lineWidth, lineCap: .round)
                    )
                Circle()
                    .trim(from: 0, to: max(0.001, min(1, progress)))
                    .stroke(
                        AngularGradient(colors: tint, center: .center),
                        style: StrokeStyle(lineWidth: lineWidth, lineCap: .round)
                    )
                    .rotationEffect(.degrees(-90))
                    .animation(.easeOut(duration: 0.6), value: progress)
                VStack(spacing: 0) {
                    Text(valueText)
                        .font(Resona.Typography.title)
                        .foregroundStyle(Resona.Palette.ink)
                    if let subtitle {
                        Text(subtitle)
                            .font(.caption2)
                            .foregroundStyle(Resona.Palette.inkFaint)
                    }
                }
            }
            .aspectRatio(1, contentMode: .fit)
        }
    }
}

// MARK: StickerStateCard — tinted circle sticker + label + value.
//
// Mockup-style state tile. Replaces the flatter MetricCard in places that
// want personality (Now tab quick stats). Icon lives in a tinted circle
// so the card reads at a glance even before you parse the number.

struct StickerStateCard: View {
    let title: String
    let value: String
    let icon: String       // SF Symbol name
    var tint: Color = Resona.Palette.lavender
    var subtitle: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            sticker
            // Eyebrow label — uppercase tracked, design-system style
            Text(title.uppercased())
                .font(Resona.Typography.label)
                .tracking(0.7)
                .foregroundStyle(Resona.Palette.inkFaint)
            // Big value — Playfair-style serif so it reads as a number
            Text(value)
                .font(.system(size: 26, weight: .bold, design: .serif))
                .foregroundStyle(Resona.Palette.ink)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(subtitle ?? " ")  // reserve a line so cards w/o subtitle stay tall
                .font(Resona.Typography.body2)
                .foregroundStyle(Resona.Palette.inkSoft)
                .lineLimit(1)
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .resonaCard(tint: tint.opacity(0.18))
    }

    private var sticker: some View {
        ZStack {
            Circle()
                .fill(
                    LinearGradient(
                        colors: [tint, tint.opacity(0.7)],
                        startPoint: .topLeading, endPoint: .bottomTrailing
                    )
                )
                .frame(width: 44, height: 44)
                .overlay(
                    Circle().strokeBorder(Color.white.opacity(0.6), lineWidth: 1)
                )
                .shadow(color: tint.opacity(0.4), radius: 6, x: 0, y: 3)
            Image(systemName: icon)
                .font(.system(size: 20, weight: .semibold))
                .foregroundStyle(.white)
        }
    }
}

// MARK: DailyQuestCard — donut + cheer message + plain-English subtitle.
//
// Dispels the "what does this number mean" ambiguity from the bare
// donut: explicit "X / 60m today" line + cheer that adapts as you cross
// 25 / 50 / 75 / 100 % so the user can see the goal is moving.

struct DailyQuestCard: View {
    var minutesToday: Double
    var goalMinutes: Int

    private var progress: Double {
        guard goalMinutes > 0 else { return 0 }
        return min(1.0, max(0.0, minutesToday / Double(goalMinutes)))
    }

    private var pct: Int { Int((progress * 100).rounded()) }

    private var cheer: String {
        switch pct {
        case 0..<10:   return "Begin when ready"
        case 10..<35:  return "Nice start ✿"
        case 35..<70:  return "Great momentum"
        case 70..<100: return "Almost there ✦"
        default:       return "Quest complete!"
        }
    }

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            DonutProgress(
                progress: progress,
                lineWidth: 9,
                label: "",
                valueText: "\(pct)%",
                subtitle: nil
            )
            .frame(width: 64, height: 64)

            VStack(alignment: .leading, spacing: 3) {
                Text("Daily quest".uppercased())
                    .font(Resona.Typography.label)
                    .tracking(0.7)
                    .foregroundStyle(Resona.Palette.inkFaint)
                Text("\(Int(minutesToday)) / \(goalMinutes) min")
                    .font(.system(size: 16, weight: .semibold, design: .serif))
                    .foregroundStyle(Resona.Palette.ink)
                Text(cheer)
                    .font(Resona.Typography.caption)
                    .foregroundStyle(Resona.Palette.lavender)
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .resonaCard(tint: Resona.Palette.butter.opacity(0.32))
        .help("Minutes of EEG captured today across all sessions, vs your \(goalMinutes)-minute daily focus goal. Resets at midnight.")
    }
}

// MARK: PrivacyMusePill — small "Privacy first" lock card matching mockup.

struct PrivacyMusePill: View {
    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Resona.Palette.sky, Resona.Palette.lavender],
                            startPoint: .topLeading, endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 44, height: 44)
                Image(systemName: "lock.shield.fill")
                    .foregroundStyle(.white)
                    .font(.system(size: 20, weight: .semibold))
            }
            VStack(alignment: .leading, spacing: 3) {
                Text("Privacy first")
                    .font(Resona.Typography.headline)
                    .foregroundStyle(Resona.Palette.ink)
                Text("Raw EEG never leaves this Mac")
                    .font(Resona.Typography.caption)
                    .foregroundStyle(Resona.Palette.inkSoft)
                    .lineLimit(2)
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .resonaCard(tint: Resona.Palette.sky.opacity(0.22))
    }
}

// MARK: MuseDevicePill — Muse-2 device card matching mockup footer.

struct MuseDevicePill: View {
    let connected: Bool
    let batteryPct: Double?

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Resona.Palette.lavender, Resona.Palette.lilac],
                            startPoint: .topLeading, endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 44, height: 44)
                Image(systemName: "brain.head.profile")
                    .foregroundStyle(.white)
                    .font(.system(size: 18, weight: .semibold))
            }
            VStack(alignment: .leading, spacing: 3) {
                Text("Muse 2")
                    .font(Resona.Typography.headline)
                    .foregroundStyle(Resona.Palette.ink)
                HStack(spacing: 4) {
                    Circle()
                        .fill(connected ? Resona.Palette.focus : Resona.Palette.coral)
                        .frame(width: 7, height: 7)
                    Text(connected ? "Connected" : "Offline")
                        .font(Resona.Typography.caption)
                        .foregroundStyle(Resona.Palette.inkSoft)
                    if let p = batteryPct {
                        Text(String(format: "· %.0f%%", p))
                            .font(Resona.Typography.caption.monospacedDigit())
                            .foregroundStyle(Resona.Palette.inkFaint)
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .resonaCard(tint: Resona.Palette.lavender.opacity(0.20))
    }
}
