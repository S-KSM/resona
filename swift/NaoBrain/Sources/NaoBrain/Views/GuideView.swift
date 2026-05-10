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
            .padding()
        }
    }

    private var intro: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("What you're looking at")
                .font(.title2).fontWeight(.semibold)
            Text("Resona reads your scalp electrical activity through 4 dry electrodes on the Muse band, splits it into frequency bands, and turns those into one number you can act on. Here's what each piece means.")
                .foregroundStyle(.secondary)
        }
    }

    private var privacy: some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Privacy", systemImage: "lock.shield")
                .font(.headline)
            Text("Raw EEG never leaves this Mac. Only state labels (e.g. \"focused\") are passed to the local Coach LLM. Nothing is uploaded.")
                .font(.callout)
                .foregroundStyle(.secondary)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct BandsCard: View {
    private let rows: [(String, String, String, String, Color)] = [
        ("δ", "Delta",  "0.5–4 Hz", "Deep sleep, unconsciousness. High while awake = drowsy / sick / micro-lapse. Use as a fatigue gauge.", .purple),
        ("θ", "Theta",  "4–8 Hz",  "Drifting, meditative, creative. Frontal θ during deep work = flow. Posterior θ = nodding off. Context matters.", .indigo),
        ("α", "Alpha",  "8–13 Hz", "Relaxed wakeful, idling. Drops when you focus. Asymmetry between left and right α = mood/approach axis.", Color(red: 0.55, green: 0.75, blue: 0.95)),
        ("β", "Beta",   "13–30 Hz","Alert, engaged, problem-solving. Low β = calm focus, mid β = active thinking, high β = anxiety. Drives Focus Coefficient.", .green),
        ("γ", "Gamma",  "30+ Hz", "Feature binding, attention spikes, 'aha' moments. Easily polluted by jaw/muscle artifact — soft signal on this device.", .orange),
    ]
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Frequency bands").font(.headline)
            ForEach(rows, id: \.1) { sym, name, hz, what, color in
                HStack(alignment: .top, spacing: 10) {
                    Text(sym)
                        .font(.title2.monospaced())
                        .frame(width: 32, alignment: .leading)
                        .foregroundStyle(color)
                    VStack(alignment: .leading, spacing: 2) {
                        HStack {
                            Text(name).font(.headline)
                            Text(hz).font(.caption.monospaced()).foregroundStyle(.secondary)
                        }
                        Text(what).font(.callout).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
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
            Text("Electrodes (4 channels)").font(.headline)
            Text("Standard 10-20 placement. Frontal pair drives the engagement read; ear pair anchors the reference and catches blinks.")
                .font(.caption).foregroundStyle(.secondary)
            ForEach(rows, id: \.0) { ch, where_, region, what in
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text(ch).font(.headline.monospaced()).frame(width: 50, alignment: .leading)
                        Text(where_).font(.callout)
                    }
                    Text("\(region) — \(what)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .padding(.leading, 50)
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct DerivedCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Derived signals").font(.headline)

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
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private func metricRow(_ name: String, _ formula: String, _ what: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(name).font(.headline)
                Text(formula).font(.caption.monospaced()).foregroundStyle(.secondary)
            }
            Text(what).font(.callout).foregroundStyle(.secondary)
        }
    }
}
