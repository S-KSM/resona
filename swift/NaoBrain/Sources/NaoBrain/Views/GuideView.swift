import SwiftUI

/// What the user is looking at. Reference card for EEG bands + electrode
/// channels — read once, never wonder "what is alpha again?" mid-session.
struct GuideView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                intro
                BandsCard()
                ChannelsCard()
                DerivedCard()
                privacy
                Spacer()
            }
            .padding(20)
        }
    }

    private var intro: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("What you're looking at")
                .font(Resona.Typography.title)
                .foregroundStyle(Resona.Palette.ink)
            Text("Resona reads your scalp electrical activity through 4 dry electrodes on the Muse band, splits it into frequency bands, and turns those into one number you can act on. Here's what each piece means.")
                .font(Resona.Typography.body)
                .foregroundStyle(Resona.Palette.inkSoft)
        }
    }

    private var privacy: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "lock.shield.fill")
                .font(.title2)
                .foregroundStyle(Resona.Palette.sky)
            VStack(alignment: .leading, spacing: 4) {
                Text("Privacy")
                    .font(Resona.Typography.headline)
                    .foregroundStyle(Resona.Palette.ink)
                Text("Raw EEG never leaves this Mac. Only state labels (e.g. \"focused\") are passed to the local Coach LLM. Nothing is uploaded.")
                    .font(Resona.Typography.body)
                    .foregroundStyle(Resona.Palette.inkSoft)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .resonaCard(tint: Resona.Palette.sky.opacity(0.25))
    }
}

private struct BandsCard: View {
    private let rows: [(String, String, String, String, Color)] = [
        ("δ", "Delta",  "0.5–4 Hz", "Deep sleep, unconsciousness. High while awake = drowsy / sick / micro-lapse. Use as a fatigue gauge.", Resona.Palette.lavender),
        ("θ", "Theta",  "4–8 Hz",  "Drifting, meditative, creative. Frontal θ during deep work = flow. Posterior θ = nodding off. Context matters.", Resona.Palette.lilac),
        ("α", "Alpha",  "8–13 Hz", "Relaxed wakeful, idling. Drops when you focus. Asymmetry between left and right α = mood/approach axis.", Resona.Palette.sky),
        ("β", "Beta",   "13–30 Hz","Alert, engaged, problem-solving. Low β = calm focus, mid β = active thinking, high β = anxiety. Drives Focus Coefficient.", Resona.Palette.mint),
        ("γ", "Gamma",  "30+ Hz", "Feature binding, attention spikes, 'aha' moments. Easily polluted by jaw/muscle artifact — soft signal on this device.", Resona.Palette.peach),
    ]
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Frequency bands")
                .font(Resona.Typography.headline)
                .foregroundStyle(Resona.Palette.ink)
            ForEach(rows, id: \.1) { sym, name, hz, what, color in
                HStack(alignment: .top, spacing: 12) {
                    Text(sym)
                        .font(.system(size: 28, weight: .semibold, design: .serif).italic())
                        .frame(width: 36, alignment: .leading)
                        .foregroundStyle(color)
                    VStack(alignment: .leading, spacing: 2) {
                        HStack {
                            Text(name)
                                .font(Resona.Typography.headline)
                                .foregroundStyle(Resona.Palette.ink)
                            Text(hz)
                                .font(.caption.monospaced())
                                .foregroundStyle(Resona.Palette.inkFaint)
                        }
                        Text(what)
                            .font(Resona.Typography.body)
                            .foregroundStyle(Resona.Palette.inkSoft)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .resonaCard(tint: Color.white.opacity(0.7))
    }
}

private struct ChannelsCard: View {
    private let rows: [(String, String, String, String)] = [
        ("TP9",  "Left mastoid (behind left ear)",  "Left temporal-parietal",  "Auditory processing, language, verbal memory. Catches eye-blink artifacts."),
        ("AF7",  "Left forehead",                   "Left prefrontal cortex",  "Planning, working memory, approach motivation, positive affect."),
        ("AF8",  "Right forehead",                  "Right prefrontal cortex", "Vigilance, error monitoring, withdrawal/negative affect."),
        ("TP10", "Right mastoid (behind right ear)","Right temporal-parietal", "Spatial / musical / holistic attention. Reference + artifact catcher."),
    ]
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Electrodes (4 channels)")
                .font(Resona.Typography.headline)
                .foregroundStyle(Resona.Palette.ink)
            Text("Standard 10-20 placement. Frontal pair drives the engagement read; ear pair anchors the reference and catches blinks.")
                .font(Resona.Typography.caption)
                .foregroundStyle(Resona.Palette.inkFaint)
            ForEach(rows, id: \.0) { ch, where_, region, what in
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text(ch)
                            .font(.callout.monospaced().weight(.semibold))
                            .frame(width: 50, alignment: .leading)
                            .foregroundStyle(Resona.Palette.lavender)
                        Text(where_)
                            .font(Resona.Typography.body)
                            .foregroundStyle(Resona.Palette.ink)
                    }
                    Text("\(region) — \(what)")
                        .font(Resona.Typography.caption)
                        .foregroundStyle(Resona.Palette.inkSoft)
                        .padding(.leading, 50)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .resonaCard(tint: Color.white.opacity(0.7))
    }
}

private struct DerivedCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Derived signals")
                .font(Resona.Typography.headline)
                .foregroundStyle(Resona.Palette.ink)

            metricRow(
                "Focus Coefficient",
                "F = β / α",
                "The headline number. High = engaged, low = relaxed. Resona reports it as `focus_ema` (smoothed) and `focus` (raw)."
            )
            metricRow(
                "Frontal Focus",
                "F over AF7 + AF8 only",
                "Engagement read using just the prefrontal pair — usually the cleanest 'am I cognitively working' signal on this device."
            )
            metricRow(
                "Frontal Asymmetry",
                "log(α_AF8) − log(α_AF7)",
                "Positive = approach/positive affect; negative = withdrawal/avoidance. Mood proxy, not a mood diagnosis."
            )
            metricRow(
                "Arousal Index",
                "(β + γ) / α",
                "Activation level, regardless of valence. High during both excitement and stress."
            )
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .resonaCard(tint: Resona.Palette.butter.opacity(0.35))
    }

    private func metricRow(_ name: String, _ formula: String, _ what: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(name)
                    .font(Resona.Typography.headline)
                    .foregroundStyle(Resona.Palette.ink)
                Text(formula)
                    .font(.caption.monospaced())
                    .foregroundStyle(Resona.Palette.peach)
            }
            Text(what)
                .font(Resona.Typography.body)
                .foregroundStyle(Resona.Palette.inkSoft)
        }
    }
}
