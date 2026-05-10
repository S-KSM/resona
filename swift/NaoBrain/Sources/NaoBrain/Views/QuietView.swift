import SwiftUI

/// 5th tab: Gatekeeper status, manual override, queued-pings surface, and a
/// brutally honest disclaimer about what we can and cannot suppress on macOS.
struct QuietView: View {
    @EnvironmentObject var client: NaoClient
    @State private var showFocusModeHelp = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header

                statusCard

                overrideCard

                queuedCard

                releasedCard

                honestyCard
            }
            .padding(20)
            .frame(maxWidth: 720)
        }
    }

    // MARK: header

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Quiet")
                .font(.system(size: 28, weight: .semibold))
            Text("The Gatekeeper decides when your AI agents may speak.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: status card

    private var statusCard: some View {
        let s = client.gatekeeper
        return HStack(alignment: .center, spacing: 16) {
            Circle()
                .fill(s?.quiet == true ? Color.orange : Color.green)
                .frame(width: 14, height: 14)
            VStack(alignment: .leading, spacing: 2) {
                Text(s?.quiet == true ? "QUIET — agents are deferring." : "OPEN — agents may speak.")
                    .font(.headline)
                if let s = s {
                    Text("label: \(s.lastLabel) · reason: \(s.lastDecisionReason) · queued: \(s.queuedCount)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } else {
                    Text("Sidecar offline — no Gatekeeper status.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: override card

    private var overrideCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Manual override")
                .font(.headline)
            Text("Sticky for 60 s before the FSM resumes control.")
                .font(.caption)
                .foregroundStyle(.secondary)
            HStack(spacing: 10) {
                Button("Force QUIET") {
                    Task { await client.overrideGatekeeper("QUIET") }
                }
                Button("Force OPEN") {
                    Task { await client.overrideGatekeeper("OPEN") }
                }
                Spacer()
                if FocusModeBridge.quietOnAvailable() && FocusModeBridge.quietOffAvailable() {
                    Label("Focus shortcuts installed", systemImage: "checkmark.seal.fill")
                        .foregroundStyle(.green)
                        .font(.caption)
                } else {
                    Button {
                        showFocusModeHelp = true
                    } label: {
                        Label("Set up Focus shortcuts…", systemImage: "exclamationmark.triangle")
                            .font(.caption)
                    }
                    .buttonStyle(.link)
                }
            }
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
        .popover(isPresented: $showFocusModeHelp) {
            focusModeHelp
        }
    }

    // MARK: queued

    private var queuedCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Queued pings")
                    .font(.headline)
                Spacer()
                Text("\(client.queuedPings.count) waiting")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text("Cooperating agents that asked `should_interrupt` and got `allow=false` may queue a one-line summary. Peek without draining; release surfaces them now.")
                .font(.caption)
                .foregroundStyle(.secondary)

            if client.queuedPings.isEmpty {
                Text("Queue empty.")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            } else {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(client.queuedPings) { p in
                        HStack(alignment: .top, spacing: 8) {
                            urgencyDot(p.urgency)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(p.source).font(.caption).foregroundStyle(.secondary)
                                Text(p.summary).font(.body)
                            }
                            Spacer()
                        }
                    }
                }
            }

            HStack {
                Button("Release all & view") {
                    Task { await client.overrideGatekeeper("release") }
                }
                .disabled(client.queuedPings.isEmpty)
                Spacer()
            }
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: last released

    @ViewBuilder
    private var releasedCard: some View {
        if !client.lastReleased.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                Text("Just released (\(client.lastReleased.count))")
                    .font(.headline)
                ForEach(client.lastReleased) { p in
                    HStack(alignment: .top, spacing: 8) {
                        urgencyDot(p.urgency)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.source).font(.caption).foregroundStyle(.secondary)
                            Text(p.summary).font(.body)
                        }
                    }
                }
            }
            .padding(16)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
        }
    }

    private func urgencyDot(_ urgency: String) -> some View {
        let color: Color = {
            switch urgency.lowercased() {
            case "high": return .red
            case "medium": return .orange
            default: return .gray
            }
        }()
        return Circle().fill(color).frame(width: 8, height: 8).padding(.top, 5)
    }

    // MARK: honesty card

    private var honestyCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("What we don't do", systemImage: "info.circle")
                .font(.headline)
            Text("macOS does not let third-party apps intercept Slack / Mail / Messages payloads. Resona's Gatekeeper is **advisory** — cooperating agents (Claude, Cursor, custom MCP clients) call `should_interrupt` and honor the answer. The Focus-mode bridge above flips macOS's own Focus, which silences whatever you've already configured Focus to silence.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: focus mode help popover

    private var focusModeHelp: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Set up Focus-mode shortcuts").font(.headline)
            Text("Open the **Shortcuts** app and create two shortcuts that toggle your preferred Focus:")
                .font(.caption)
            VStack(alignment: .leading, spacing: 4) {
                Text("• Name: \"Resona Quiet On\" — action: Set Focus → Do Not Disturb → Turn On")
                Text("• Name: \"Resona Quiet Off\" — action: Set Focus → Do Not Disturb → Turn Off")
            }
            .font(.caption.monospaced())
            Text("Resona detects them by name and runs them on QUIET ↔ OPEN edges.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(16)
        .frame(width: 360)
    }
}
