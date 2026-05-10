import SwiftUI

struct RootView: View {
    @EnvironmentObject var client: NaoClient
    @State private var tab: Tab = .now

    /// Tabs are organized by user goal, not subsystem.
    /// - now: verdict + minimal stats + inline Coach (LLM Q&A) panel
    /// - sessions: review or record a labeled session
    /// - guide: "what am I looking at?" — wave + channel reference
    /// - tune: setup, calibrate, quiet rules, voice — all the plumbing
    enum Tab: String, CaseIterable, Identifiable {
        case now      = "Now"
        case sessions = "Sessions"
        case guide    = "Guide"
        case tune     = "Tune"
        var id: String { rawValue }

        var symbol: String {
            switch self {
            case .now:      return "sun.max.fill"
            case .sessions: return "waveform.path.ecg"
            case .guide:    return "book.pages.fill"
            case .tune:     return "slider.horizontal.3"
            }
        }

        var tint: Color {
            switch self {
            case .now:      return Resona.Palette.peach
            case .sessions: return Resona.Palette.lavender
            case .guide:    return Resona.Palette.sky
            case .tune:     return Resona.Palette.mint
            }
        }
    }

    var body: some View {
        ZStack {
            Resona.Gradients.appBackground.ignoresSafeArea()

            VStack(spacing: 0) {
                topBar
                Group {
                    switch tab {
                    case .now:      NowView()
                    case .sessions: SessionsView()
                    case .guide:    GuideView()
                    case .tune:     TuneView()
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
    }

    private var topBar: some View {
        HStack(spacing: 14) {
            // Wordmark — serif italic, brand mark via SF symbol moon-rise stand-in.
            HStack(spacing: 6) {
                Image(systemName: "sun.haze.fill")
                    .foregroundStyle(Resona.Palette.peach)
                    .font(.title3)
                VStack(alignment: .leading, spacing: -2) {
                    Text("Resona").font(Resona.Typography.title)
                        .foregroundStyle(Resona.Palette.ink)
                    Text("your mind, in tune")
                        .font(.caption2)
                        .foregroundStyle(Resona.Palette.inkFaint)
                }
            }
            .padding(.trailing, 6)

            // Pastel pill nav.
            HStack(spacing: 6) {
                ForEach(Tab.allCases) { t in
                    Button {
                        tab = t
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: t.symbol).font(.caption)
                            Text(t.rawValue)
                        }
                        .resonaPill(active: tab == t, tint: t.tint)
                    }
                    .buttonStyle(.plain)
                }
            }

            Spacer()

            ConnectionPill()
        }
        .padding(.horizontal, 18)
        .padding(.top, 14)
        .padding(.bottom, 10)
    }
}

struct ConnectionPill: View {
    @EnvironmentObject var client: NaoClient
    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(client.isConnected ? Resona.Palette.focus : Resona.Palette.alert)
                .frame(width: 8, height: 8)
            Text(client.isConnected ? "Sidecar online" : "Sidecar offline")
                .font(Resona.Typography.caption)
                .foregroundStyle(Resona.Palette.inkSoft)
        }
        .padding(.horizontal, 10).padding(.vertical, 6)
        .background(Capsule().fill(Color.white.opacity(0.7)))
        .overlay(Capsule().strokeBorder(Color.white, lineWidth: 1))
        .help(client.lastError ?? (client.isConnected ? "Streaming." : "Run `uv run nao-sidecar`."))
    }
}
