import SwiftUI

struct RootView: View {
    @EnvironmentObject var client: NaoClient
    @State private var tab: Tab = .now

    /// Tabs are organized by user goal, not subsystem.
    /// - now: "what should I do right now?" — verdict + minimal stats
    /// - sessions: "review or record a labeled session"
    /// - coach: LLM Q&A about your state. Skeptic surfaces inline as a callout.
    /// - guide: "what am I looking at?" — wave + channel reference
    /// - tune: setup, calibrate, quiet rules, voice — all the plumbing
    enum Tab: String, CaseIterable, Identifiable {
        case now      = "Now"
        case sessions = "Sessions"
        case coach    = "Coach"
        case guide    = "Guide"
        case tune     = "Tune"
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
                case .now:      NowView()
                case .sessions: SessionsView()
                case .coach:    CoachView()
                case .guide:    GuideView()
                case .tune:     TuneView()
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
