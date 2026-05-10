import SwiftUI

/// Verdict-first home tab. Answers the user's actual question — "should I
/// keep going, take a break, or fix something?" — in one sentence, with the
/// reasoning collapsible underneath.
struct NowView: View {
    @EnvironmentObject var client: NaoClient
    @State private var showDetails = false
    @State private var restarting = false
    @State private var now = Date()

    private let stuckTimer = Timer.publish(every: 1.0, on: .main, in: .common).autoconnect()

    /// Heuristic for "Muse is stuck": no fresh frame for >8 s. Frame.ts is
    /// emitted by the Muse as a Unix epoch when live; for synthetic it's
    /// monotonic, but the wall-clock comparison still works because both are
    /// updated as samples arrive.
    private var frameAgeSeconds: Double? {
        guard let ts = client.latestFrame?.ts else { return nil }
        // Synthetic ts is monotonic (~ low number) → don't false-alarm. Only
        // treat as stuck when ts looks like Unix epoch (post-2000).
        guard ts > 946_684_800 else { return nil }
        return now.timeIntervalSince1970 - ts
    }

    private var isStuck: Bool {
        (frameAgeSeconds ?? 0) > 8.0
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if isStuck { stuckBanner }

                HStack {
                    SessionStrip()
                    Spacer()
                    BatteryPill(battery: client.battery)
                }

                verdictCard

                quickStats

                ContactCoachBanner(
                    frame: client.latestFrame,
                    quality: client.signalQuality?.signalQuality
                )

                DisclosureGroup("Show signal detail", isExpanded: $showDetails) {
                    VStack(alignment: .leading, spacing: 12) {
                        if let q = client.signalQuality?.signalQuality {
                            SignalQualityRow(quality: q)
                        }
                        ArtifactBanner(frame: client.latestFrame)
                        BandPreviewRow(frame: client.latestFrame)
                    }
                    .padding(.top, 8)
                }
                .padding(12)
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 10))

                Spacer()
            }
            .padding()
            .onReceive(stuckTimer) { now = $0 }
        }
    }

    private var stuckBanner: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.arrow.triangle.2.circlepath")
                .font(.title2)
                .foregroundStyle(.orange)
            VStack(alignment: .leading, spacing: 2) {
                Text("Signal stuck")
                    .font(.headline)
                Text(String(
                    format: "No fresh frames for %.0f s. Restart to reconnect the Muse.",
                    frameAgeSeconds ?? 0
                ))
                .font(.caption)
                .foregroundStyle(.secondary)
            }
            Spacer()
            restartButton
        }
        .padding(14)
        .background(Color.orange.opacity(0.10), in: RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(Color.orange.opacity(0.35), lineWidth: 1)
        )
    }

    private var restartButton: some View {
        Button {
            Task {
                restarting = true
                await client.restartPipeline()
                try? await Task.sleep(nanoseconds: 1_500_000_000)
                restarting = false
            }
        } label: {
            HStack(spacing: 6) {
                if restarting {
                    ProgressView().scaleEffect(0.6)
                } else {
                    Image(systemName: "arrow.clockwise")
                }
                Text(restarting ? "Restarting…" : "Restart signal")
            }
        }
        .buttonStyle(.borderedProminent)
        .tint(.orange)
        .disabled(restarting)
    }

    private var verdictCard: some View {
        let v = client.verdict
        return VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Image(systemName: v?.systemImage ?? "circle.dotted")
                    .font(.title)
                    .foregroundStyle(v?.color ?? .secondary)
                Text(v?.headline ?? "Warming up.")
                    .font(.title)
                    .fontWeight(.semibold)
                Spacer()
                Button {
                    Task {
                        restarting = true
                        await client.restartPipeline()
                        try? await Task.sleep(nanoseconds: 1_500_000_000)
                        restarting = false
                    }
                } label: {
                    if restarting {
                        ProgressView().scaleEffect(0.6)
                    } else {
                        Image(systemName: "arrow.clockwise").font(.title3)
                    }
                }
                .buttonStyle(.borderless)
                .help("Restart signal — reconnects the Muse pipeline if it's stuck.")
                .disabled(restarting)
            }
            if let detail = v?.detail, !detail.isEmpty {
                Text(detail)
                    .font(.body)
                    .foregroundStyle(.secondary)
            }
            if let action = v?.action, !action.isEmpty {
                HStack(spacing: 8) {
                    Image(systemName: "arrow.turn.down.right")
                        .foregroundStyle(.secondary)
                    Text(action).font(.callout)
                }
                .padding(.top, 2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(
            RoundedRectangle(cornerRadius: 14)
                .fill((client.verdict?.color ?? .secondary).opacity(0.08))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .strokeBorder((client.verdict?.color ?? .secondary).opacity(0.25), lineWidth: 1)
        )
    }

    private var quickStats: some View {
        HStack(spacing: 12) {
            MetricCard(
                title: "Focus (frontal)",
                value: client.latestFrame?.frontalFocusEma.map { String(format: "%.2f", $0) } ?? "—",
                tint: client.verdict?.color ?? .secondary
            )
            MetricCard(
                title: "Label",
                value: client.latestFrame?.label ?? "—"
            )
            MetricCard(
                title: client.gatekeeper?.quiet == true ? "Quiet ON" : "Quiet OFF",
                value: client.gatekeeper.map { "\($0.queuedCount) held" } ?? "—",
                tint: client.gatekeeper?.quiet == true ? .blue : .secondary
            )
        }
    }
}

/// Per-band relative power. Each band is shown as % of total spectral power
/// (sums to ~100), so the user has a real 0–100 range to interpret without
/// per-user calibration. Reference bands ("typical awake adult") are marked
/// with a faint gray tick so users know where their reading sits.
struct BandPreviewRow: View {
    let frame: FocusFrame?

    /// Symbol, reference low/high (% of total power, awake adult eyes-open),
    /// keypath into FocusFrame for the relative value, and a one-line hint.
    private let bands: [(String, ClosedRange<Double>, KeyPath<FocusFrame, Double?>, String, Color)] = [
        ("δ delta", 15...35, \.deltaRel, "deep sleep / drowsy lapses",  .purple),
        ("θ theta", 10...25, \.thetaRel, "drifting / flow / drowsy",    .indigo),
        ("α alpha", 15...35, \.alphaRel, "relaxed wakeful",              Color(red: 0.55, green: 0.75, blue: 0.95)),
        ("β beta",  10...30, \.betaRel,  "alert / engaged",              .green),
        ("γ gamma",  5...20, \.gammaRel, "binding / 'aha' (noisy)",      .orange),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Band power")
                    .font(.subheadline).foregroundStyle(.secondary)
                Spacer()
                Text("% of total · gray ticks = typical range")
                    .font(.caption2).foregroundStyle(.secondary)
            }
            ForEach(bands, id: \.0) { sym, ref, kp, hint, color in
                BandBar(
                    label: sym, hint: hint, color: color, refRange: ref,
                    relativePct: frame.flatMap { $0[keyPath: kp] }.map { $0 * 100 }
                )
            }
        }
    }
}

private struct BandBar: View {
    let label: String
    let hint: String
    let color: Color
    let refRange: ClosedRange<Double>     // expressed in percent (0-100)
    let relativePct: Double?

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 8) {
                Text(label)
                    .font(.callout.monospaced())
                    .frame(width: 70, alignment: .leading)
                    .foregroundStyle(color)
                Text(hint).font(.caption).foregroundStyle(.secondary)
                Spacer()
                Text(relativePct.map { String(format: "%.0f%%", $0) } ?? "—")
                    .font(.callout.monospaced())
                    .foregroundStyle(.primary)
                    .frame(width: 50, alignment: .trailing)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(.quaternary)
                    // Reference range — faint shaded band.
                    RoundedRectangle(cornerRadius: 2)
                        .fill(.tertiary)
                        .frame(
                            width: geo.size.width * (refRange.upperBound - refRange.lowerBound) / 100,
                            height: 6
                        )
                        .offset(x: geo.size.width * refRange.lowerBound / 100)
                    // Actual reading.
                    if let pct = relativePct {
                        let clamped = max(0, min(100, pct))
                        RoundedRectangle(cornerRadius: 3)
                            .fill(color)
                            .frame(width: geo.size.width * clamped / 100, height: 8)
                    }
                }
            }
            .frame(height: 8)
        }
    }
}

/// Battery pill — colored dot + percentage. Shows "—" when source is
/// synthetic or telemetry hasn't arrived yet (Muse pushes every ~5 s).
struct BatteryPill: View {
    let battery: BatteryStatus?

    private var pct: Double? { battery?.batteryPct }
    private var stale: Bool { battery?.stale ?? true }

    private var icon: String {
        guard let p = pct else { return "battery.0" }
        switch p {
        case ..<10:  return "battery.0"
        case ..<35:  return "battery.25"
        case ..<65:  return "battery.50"
        case ..<90:  return "battery.75"
        default:     return "battery.100"
        }
    }

    private var tint: Color {
        guard let p = pct, !stale else { return .secondary }
        if p < 15 { return .red }
        if p < 30 { return .orange }
        return .green
    }

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon).foregroundStyle(tint)
            Text(pct.map { String(format: "%.0f%%", $0) } ?? "—")
                .font(.callout.monospacedDigit())
                .foregroundStyle(stale ? .secondary : .primary)
        }
        .padding(.horizontal, 10).padding(.vertical, 5)
        .background(.thinMaterial, in: Capsule())
        .help(stale
              ? "Headband battery: no recent telemetry."
              : "Muse headband battery.")
    }
}
