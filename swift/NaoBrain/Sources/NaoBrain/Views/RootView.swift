import SwiftUI

struct RootView: View {
    @EnvironmentObject var client: NaoClient
    @State private var tab: Tab = .live

    enum Tab: String, CaseIterable, Identifiable {
        case live = "Live"
        case sessions = "Sessions"
        case setup = "Setup"
        case calibrate = "Calibrate"
        case coach = "Coach"
        case quiet = "Quiet"
        case skeptic = "Skeptic"
        var id: String { rawValue }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Picker("", selection: $tab) {
                    ForEach(Tab.allCases) { t in
                        Text(t.rawValue).tag(t)
                    }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 480)

                Spacer()

                ConnectionPill()
            }
            .padding(.horizontal)
            .padding(.top, 12)
            .padding(.bottom, 8)

            Divider()

            Group {
                switch tab {
                case .live:      LiveView()
                case .sessions:  SessionsView()
                case .setup:     SetupView()
                case .calibrate: CalibrateView()
                case .coach:     CoachView()
                case .quiet:     QuietView()
                case .skeptic:   SkepticView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

struct ConnectionPill: View {
    @EnvironmentObject var client: NaoClient
    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(client.isConnected ? Color.green : Color.red)
                .frame(width: 8, height: 8)
            Text(client.isConnected ? "Sidecar online" : "Sidecar offline")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .help(client.lastError ?? (client.isConnected ? "Streaming." : "Run `uv run nao-sidecar`."))
    }
}
