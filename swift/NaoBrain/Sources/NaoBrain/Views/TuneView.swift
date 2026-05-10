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
    }

    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $sub) {
                ForEach(Sub.allCases) { s in
                    Text(s.rawValue).tag(s)
                }
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 460)
            .padding(.horizontal)
            .padding(.vertical, 8)

            Divider()

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
/// Most users never need this tab; lives under Tune so it stays out of the
/// daily flow.
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
                        .foregroundStyle(.secondary)
                    Text("Once connected, Resona will fuse SpO2 + HRV with EEG to flag breath-related focus crashes (apnea, mouth-breathing, slumped posture) and unlock the Breath Coach loop.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding()
        }
    }

    @ViewBuilder
    private func section<C: View>(_ title: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.headline)
            content()
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}
