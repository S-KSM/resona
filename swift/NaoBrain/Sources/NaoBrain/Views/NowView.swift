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

                SessionStrip()

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

/// Compact per-band readout with one-line interpretations. Shows the user
/// what each frequency band is *for* while they look at the numbers — no
/// Wikipedia trip required.
struct BandPreviewRow: View {
    let frame: FocusFrame?
    private let bands: [(String, KeyPath<FocusFrame, Double>, String)] = [
        ("δ delta", \.delta, "deep sleep / drowsy lapses"),
        ("θ theta", \.theta, "drifting / flow / drowsy"),
        ("α alpha", \.alpha, "relaxed wakeful"),
        ("β beta",  \.beta,  "alert / engaged"),
        ("γ gamma", \.gamma, "binding / 'aha' (noisy)"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Band power").font(.subheadline).foregroundStyle(.secondary)
            ForEach(bands, id: \.0) { name, kp, hint in
                HStack {
                    Text(name).font(.callout.monospaced()).frame(width: 70, alignment: .leading)
                    Text(frame.map { String(format: "%.2f", $0[keyPath: kp]) } ?? "—")
                        .font(.callout.monospaced())
                        .frame(width: 60, alignment: .trailing)
                    Text(hint).font(.caption).foregroundStyle(.secondary)
                    Spacer()
                }
            }
        }
    }
}
