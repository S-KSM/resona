import SwiftUI

/// 6th tab: Skeptic surface. Shows reward-spike state + the caution flag that
/// cooperating agents should honor before *affirming* the user's recent choice.
struct SkepticView: View {
    @EnvironmentObject var client: NaoClient

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                stateCard
                baselineCard
                cooperatingAgentsCard
                honestyCard
            }
            .padding(20)
            .frame(maxWidth: 720)
        }
    }

    // MARK: header

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Skeptic")
                .font(.system(size: 28, weight: .semibold))
            Text("Reward-spike awareness for cooperating agents.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: state card

    private var stateCard: some View {
        let s = client.appraisal
        let caution = s?.caution ?? false
        return HStack(alignment: .top, spacing: 16) {
            Circle()
                .fill(caution ? Color.orange : Color.gray.opacity(0.5))
                .frame(width: 14, height: 14)
                .padding(.top, 4)
            VStack(alignment: .leading, spacing: 4) {
                Text(caution
                     ? "Caution — recent reward burst."
                     : "No recent spike — affirmation is safe.")
                    .font(.headline)
                if let s = s {
                    Text(detailText(s))
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                } else {
                    Text("Sidecar offline — no Skeptic status.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private func detailText(_ s: AppraisalState) -> String {
        var parts: [String] = []
        if let since = s.sinceSpikeS {
            parts.append(String(format: "since spike: %.0fs", since))
        }
        if s.caution {
            parts.append(String(format: "cooldown: %.0fs", s.cooldownSeconds))
        }
        if let z = s.lastZ {
            parts.append(String(format: "last z=%.2f", z))
        }
        parts.append("reason: \(s.reason)")
        return parts.joined(separator: " · ")
    }

    // MARK: baseline card

    private var baselineCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Baseline")
                .font(.headline)
            if let s = client.appraisal {
                Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 4) {
                    GridRow {
                        Text("clean samples").foregroundStyle(.secondary)
                        Text("\(s.baselineN)").monospacedDigit()
                    }
                    GridRow {
                        Text("frontal-γ mean").foregroundStyle(.secondary)
                        Text(s.baselineMean.map { String(format: "%.3f", $0) } ?? "—").monospacedDigit()
                    }
                }
                .font(.callout)
                if s.baselineN < 60 {
                    Label("Warming up — need ~60 clean samples before spike detection arms.",
                          systemImage: "hourglass")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
            } else {
                Text("—").foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: cooperating agents

    private var cooperatingAgentsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("How agents use this")
                .font(.headline)
            Text("Cooperating agents call `get_appraisal_state` (MCP) before *affirming* a recent decision. When `caution=true` they soften, probe, or counter-cite instead of agreeing — you may be riding a reward wave and your judgment is biased toward the reinforcing option.")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text("Distinct from the Gatekeeper (which gates *interruption*); the Skeptic gates *affirmation*.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: honesty

    private var honestyCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("What this is not", systemImage: "info.circle")
                .font(.headline)
            Text("Frontal gamma over Muse's AF7+AF8 is a coarse, noisy proxy for cognitive reward — not a polygraph. Z-score is over a session-local baseline, so very long sessions or shifts in mental state will drift the threshold. Treat the caution flag as advisory texture, not a verdict.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}
