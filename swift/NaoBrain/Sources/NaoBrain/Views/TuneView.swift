import SwiftUI

/// Plumbing tab — sources, calibration, quiet-mode rules, advanced. Hidden
/// from the user's daily flow: visit once on setup, again when something
/// changes. The user goal here is "configure," not "monitor."
struct TuneView: View {
    @State private var sub: Sub = .source

    enum Sub: String, CaseIterable, Identifiable {
        case source    = "Source"
        case calibrate = "Calibrate"
        case quiet     = "Quiet rules"
        case advanced  = "Advanced"
        var id: String { rawValue }

        var symbol: String {
            switch self {
            case .source:    return "antenna.radiowaves.left.and.right"
            case .calibrate: return "scope"
            case .quiet:     return "moon.zzz.fill"
            case .advanced:  return "gearshape.2.fill"
            }
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 6) {
                ForEach(Sub.allCases) { s in
                    Button {
                        sub = s
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: s.symbol).font(.caption)
                            Text(s.rawValue)
                        }
                        .resonaPill(active: sub == s, tint: Resona.Palette.lavender)
                    }
                    .buttonStyle(.plain)
                }
                Spacer()
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 12)

            Group {
                switch sub {
                case .source:    SetupView()
                case .calibrate: CalibrateView()
                case .quiet:     QuietView()
                case .advanced:  AdvancedView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

/// Advanced — Skeptic appraisal monitor + future SpO2 / Apple Watch hookup.
struct AdvancedView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                section("Reward-spike skeptic") {
                    SkepticView()
                        .frame(minHeight: 200)
                }

                section("Pulse-ox / SpO2") {
                    Label("Apple Watch HealthKit bridge — coming soon.", systemImage: "applewatch")
                        .foregroundStyle(Resona.Palette.inkSoft)
                    Text("Once connected, Resona will fuse SpO2 + HRV with EEG to flag breath-related focus crashes (apnea, mouth-breathing, slumped posture) and unlock the Breath Coach loop.")
                        .font(Resona.Typography.caption)
                        .foregroundStyle(Resona.Palette.inkFaint)
                }
            }
            .padding(20)
        }
    }

    @ViewBuilder
    private func section<C: View>(_ title: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(Resona.Typography.headline)
                .foregroundStyle(Resona.Palette.ink)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .resonaCard(tint: Color.white.opacity(0.7))
    }
}
