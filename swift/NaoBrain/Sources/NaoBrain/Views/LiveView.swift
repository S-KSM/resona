import Charts
import SwiftUI

struct LiveView: View {
    @EnvironmentObject var client: NaoClient

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                SessionStrip()

                metricsRow

                focusChart

                bandsChart

                ContactCoachBanner(
                    frame: client.latestFrame,
                    quality: client.signalQuality?.signalQuality
                )

                ArtifactBanner(frame: client.latestFrame)

                if let q = client.signalQuality?.signalQuality {
                    SignalQualityRow(quality: q)
                }

                Spacer()
            }
            .padding()
        }
    }

    private var metricsRow: some View {
        HStack(spacing: 12) {
            MetricCard(
                title: "Focus (EMA)",
                value: client.latestFrame.map { String(format: "%.2f", $0.focusEma) } ?? "—"
            )
            MetricCard(
                title: "Frontal F (EMA)",
                value: frontalFEmaText,
                tint: Color(red: 1.0, green: 0.78, blue: 0.34)  // brand amber
            )
            MetricCard(
                title: "Latency",
                value: client.latestFrame.map { String(format: "%.0f ms", $0.latencyMs) } ?? "—",
                tint: latencyTint
            )
            MetricCard(
                title: "Label",
                value: client.latestFrame?.label ?? "—",
                tint: labelTint
            )
        }
    }

    private var frontalFEmaText: String {
        guard let v = client.latestFrame?.frontalFocusEma else { return "—" }
        return String(format: "%.2f", v)
    }

    private var latencyTint: Color {
        guard let f = client.latestFrame else { return .secondary }
        return f.latencyMs > 500 ? .red : .secondary
    }

    private var labelTint: Color {
        switch client.latestFrame?.label {
        case "deeply_focused": return .blue
        case "engaged":        return .green
        case "neutral":        return .secondary
        case "resting":        return .orange
        case "uncertain":      return .red
        default:               return .secondary
        }
    }

    private var focusChart: some View {
        let history = client.history
        let amber = Color(red: 1.0, green: 0.78, blue: 0.34)  // brand
        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                Text("Focus Coefficient over time")
                    .font(.headline)
                Spacer()
                LegendDot(color: .blue, label: "averaged")
                LegendDot(color: amber, label: "frontal")
            }
            Chart {
                ForEach(history) { f in
                    LineMark(
                        x: .value("ts", f.ts),
                        y: .value("focus", f.focus),
                        series: .value("series", "raw_avg")
                    )
                    .foregroundStyle(.blue.opacity(0.35))
                    .interpolationMethod(.linear)
                }
                ForEach(history) { f in
                    LineMark(
                        x: .value("ts", f.ts),
                        y: .value("focus_ema", f.focusEma),
                        series: .value("series", "ema_avg")
                    )
                    .foregroundStyle(.blue)
                    .interpolationMethod(.monotone)
                }
                ForEach(history) { f in
                    if let ema = f.frontalFocusEma {
                        LineMark(
                            x: .value("ts", f.ts),
                            y: .value("frontal_ema", ema),
                            series: .value("series", "ema_frontal")
                        )
                        .foregroundStyle(amber)
                        .interpolationMethod(.monotone)
                    }
                }
            }
            .chartXAxis(.hidden)
            .chartXScale(domain: focusXRange(history))
            .chartYScale(domain: focusYRange(history))
            .frame(height: 200)
        }
    }

    private func focusXRange(_ history: [FocusFrame]) -> ClosedRange<Double> {
        guard let last = history.last?.ts else { return 0...1 }
        let window: Double = 30  // seconds of history to show
        let lo = (history.first?.ts ?? last - window)
        return min(lo, last - window)...last
    }

    private func focusYRange(_ history: [FocusFrame]) -> ClosedRange<Double> {
        guard !history.isEmpty else { return 0...1 }
        var values: [Double] = []
        for f in history {
            values.append(f.focus)
            values.append(f.focusEma)
            if let v = f.frontalFocusEma { values.append(v) }
        }
        let lo = max(0, (values.min() ?? 0) - 0.1)
        let hi = (values.max() ?? 1) + 0.1
        return lo...max(hi, lo + 0.5)
    }

    private var bandsChart: some View {
        let frame = client.latestFrame
        let bands: [(String, Double)] = [
            ("delta", frame?.delta ?? 0),
            ("theta", frame?.theta ?? 0),
            ("alpha", frame?.alpha ?? 0),
            ("beta",  frame?.beta  ?? 0),
            ("gamma", frame?.gamma ?? 0),
        ]
        return VStack(alignment: .leading, spacing: 8) {
            Text("Band power (latest window)")
                .font(.headline)
            Chart {
                ForEach(bands, id: \.0) { name, value in
                    BarMark(
                        x: .value("band", name),
                        y: .value("power", value)
                    )
                }
            }
            .frame(height: 160)
        }
    }
}

struct LegendDot: View {
    let color: Color
    let label: String
    var body: some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
    }
}

struct MetricCard: View {
    let title: String
    let value: String
    var tint: Color = Resona.Palette.lavender
    var icon: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                if let icon {
                    Image(systemName: icon)
                        .font(.caption)
                        .foregroundStyle(tint)
                }
                Text(title)
                    .font(Resona.Typography.caption)
                    .foregroundStyle(Resona.Palette.inkSoft)
            }
            Text(value)
                .font(.system(.title2, design: .rounded).weight(.semibold))
                .foregroundStyle(Resona.Palette.ink)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .resonaCard(tint: tint.opacity(0.18))
    }
}

/// Loud, instructional banner shown when one or more EEG channels report
/// FLAT or noisy contact while BAD_CONTACT is in the artifact flags. Maps the
/// failing channel to a specific reseat hint so the user doesn't have to
/// remember the band geometry.
struct ContactCoachBanner: View {
    let frame: FocusFrame?
    let quality: [ChannelQuality]?

    var body: some View {
        Group {
            if let bad = badChannels(), !bad.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Label("Bad contact: \(bad.map(\.channel).joined(separator: ", "))",
                          systemImage: "exclamationmark.triangle.fill")
                        .font(.headline)
                        .foregroundStyle(.orange)
                    ForEach(bad, id: \.channel) { c in
                        HStack(alignment: .top, spacing: 6) {
                            Text(c.channel)
                                .font(.caption.weight(.semibold))
                                .frame(width: 44, alignment: .leading)
                                .foregroundStyle(.secondary)
                            Text(reseatHint(for: c.channel, verdict: c.verdict))
                                .font(.callout)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .resonaCard(tint: Resona.Palette.coral.opacity(0.15))
            }
        }
    }

    private func badChannels() -> [ChannelQuality]? {
        guard let q = quality else { return nil }
        // Only show when the frame is actually flagged BAD_CONTACT — single
        // weak channel during transient settling shouldn't nag.
        let flagged = frame?.artifact.contains("BAD_CONTACT") ?? false
        if !flagged { return nil }
        return q.filter { $0.verdict == "FLAT" || $0.verdict == "weak" || $0.verdict == "noisy" }
    }

    private func reseatHint(for channel: String, verdict: String) -> String {
        let where_: String = {
            switch channel {
            case "TP9":  return "left ear (push hair clear, press earpiece against the bony bump behind your ear)"
            case "TP10": return "right ear (push hair clear, press earpiece against the bony bump behind your ear)"
            case "AF7":  return "left forehead (band 1 cm above eyebrow, on bare skin — no hair under the pad)"
            case "AF8":  return "right forehead (band 1 cm above eyebrow, on bare skin — no hair under the pad)"
            default:     return channel
            }
        }()
        let action: String = {
            switch verdict {
            case "FLAT":   return "no signal — reseat"
            case "weak":   return "weak signal — press firmly"
            case "noisy":  return "saturated — loosen band a notch"
            default:       return verdict
            }
        }()
        return "\(action): \(where_)"
    }
}

struct ArtifactBanner: View {
    let frame: FocusFrame?
    var body: some View {
        Group {
            if let f = frame {
                if f.artifactClean {
                    Label("Signal clean", systemImage: "checkmark.seal")
                        .foregroundStyle(.green)
                } else {
                    Label("Artifacts: " + f.artifact.joined(separator: ", "),
                          systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                }
            }
        }
        .font(.callout)
    }
}

struct SignalQualityRow: View {
    let quality: [ChannelQuality]
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Per-channel signal quality")
                .font(.subheadline).foregroundStyle(.secondary)
            HStack(spacing: 12) {
                ForEach(quality) { q in
                    ChannelQualityRow(quality: q)
                }
            }
        }
    }
}
