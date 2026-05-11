import SwiftUI

/// Verdict-first home tab in Resona pastel theme. Hero banner + verdict
/// sentence, quick stats, inline Coach (LLM Q&A) panel, signal detail under
/// a disclosure. Coach used to be a separate tab; merged here so the user
/// sees their state and can ask about it without switching context.
struct NowView: View {
    @EnvironmentObject var client: NaoClient
    @State private var showDetails = false
    @State private var showCoach = false
    @State private var restarting = false
    @State private var now = Date()

    private let stuckTimer = Timer.publish(every: 1.0, on: .main, in: .common).autoconnect()

    private var frameAgeSeconds: Double? {
        guard let ts = client.latestFrame?.ts else { return nil }
        guard ts > 946_684_800 else { return nil }
        return now.timeIntervalSince1970 - ts
    }

    private var isStuck: Bool { (frameAgeSeconds ?? 0) > 8.0 }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if isStuck { stuckBanner }

                HStack {
                    SessionStrip()
                    Spacer()
                    BatteryPill(battery: client.battery)
                }

                heroVerdictCard

                quickStats

                LiveSignalPanel(
                    history: client.history,
                    windowFrames: 40,
                    isFresh: !isStuck && client.latestFrame != nil
                )

                ContactCoachBanner(
                    frame: client.latestFrame,
                    quality: client.signalQuality?.signalQuality
                )

                skepticChip

                coachPanel

                signalDetail

                footerStrip

                Spacer(minLength: 8)
            }
            .padding(20)
            .onReceive(stuckTimer) { now = $0 }
        }
    }

    // MARK: hero — sun mascot + serif italic verdict

    private var heroVerdictCard: some View {
        let v = client.verdict
        return ZStack(alignment: .topTrailing) {
            // Hero gradient surface — design-system "Aurora" wash
            HStack(alignment: .center, spacing: 24) {
                VStack(alignment: .leading, spacing: 10) {
                    Text(eyebrowText.uppercased())
                        .font(Resona.Typography.eyebrow)
                        .tracking(1.2)
                        .foregroundStyle(Resona.Palette.lavender)

                    Text(v?.headline ?? "Mind settling into focus")
                        .font(Resona.Typography.display2)
                        .foregroundStyle(Resona.Palette.ink)
                        .lineLimit(2)
                        .minimumScaleFactor(0.7)
                        .fixedSize(horizontal: false, vertical: true)

                    if let detail = v?.detail, !detail.isEmpty {
                        Text(detail)
                            .font(Resona.Typography.body)
                            .foregroundStyle(Resona.Palette.inkSoft)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    if let action = v?.action, !action.isEmpty {
                        HStack(spacing: 8) {
                            Image(systemName: "heart.fill")
                                .foregroundStyle(Resona.Palette.coral)
                                .font(.caption)
                            Text(action)
                                .font(Resona.Typography.body2)
                                .foregroundStyle(Resona.Palette.ink)
                        }
                        .padding(.top, 4)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                // SwiftUI Focus Orb — multi-layer iridescent halo,
                // breathing animation, sparkle constellation. Scales
                // crisply at any size; no PNG dependency.
                FocusOrb(
                    mood: orbMood,
                    embedded: true,
                    focusLevel: orbFocusLevel,
                    animated: true
                )
                .frame(width: 240, height: 240)
            }
            .padding(28)
            .background(
                LinearGradient(
                    colors: [
                        Resona.Palette.lilac.opacity(0.55),
                        Resona.Palette.blush.opacity(0.50),
                        Resona.Palette.sky.opacity(0.45)
                    ],
                    startPoint: .topLeading, endPoint: .bottomTrailing
                ),
                in: RoundedRectangle(cornerRadius: 24, style: .continuous)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .strokeBorder(Color.white.opacity(0.6), lineWidth: 1)
            )
            .shadow(color: Resona.Palette.lavender.opacity(0.20), radius: 14, x: 0, y: 6)

            // Top-right refresh icon — replaces the awkward inline button.
            heroRefreshButton
                .padding(14)
        }
    }

    /// Contextual eyebrow above the hero title — shifts with the verdict
    /// tone so the user knows whether the headline is good news or a
    /// nudge.
    private var eyebrowText: String {
        switch client.verdict?.tone {
        case "focused": return "Right where you need to be"
        case "ok":      return "Steady and present"
        case "calm":    return "Soft attention"
        case "fading":  return "A little drift"
        case "alert":   return "Take a breath"
        case "noisy":   return "Settling the signal"
        default:        return "Warming up"
        }
    }

    /// Picks the mascot scene that fits the current state. Quiet ON
    /// flips to the moon-cloud (rest mode); warming-up / very noisy
    /// renders the settling jelly; alert tone gives the orb wide eyes;
    /// everything else is the default content mascot.
    private var orbMood: FocusOrb.Mood {
        // Quiet ON wins — the user has chosen to disengage agents,
        // mascot should reflect that even if EEG looks "focused".
        if client.gatekeeper?.quiet == true { return .sleepy }

        // No frame yet, or signal is noisy/being-calibrated → settling.
        let frame = client.latestFrame
        let warming = frame?.frontalFocusEma == nil
        if warming { return .settling }
        if let f = frame, f.artifact.contains("BAD_CONTACT") { return .settling }

        switch client.verdict?.tone {
        case "alert", "noisy": return .alert
        default:               return .content
        }
    }

    /// Maps frontal focus EMA into the 0…1 range FocusOrb uses to drive
    /// pulse cadence. β/α typically lives in 0.4…1.5 for awake adults;
    /// we clamp to that window before normalizing.
    private var orbFocusLevel: Double? {
        guard let f = client.latestFrame?.frontalFocusEma else { return nil }
        let lo = 0.4
        let hi = 1.5
        let clamped = max(lo, min(hi, f))
        return (clamped - lo) / (hi - lo)
    }

    private var heroRefreshButton: some View {
        Button {
            Task {
                restarting = true
                await client.restartPipeline()
                try? await Task.sleep(nanoseconds: 1_500_000_000)
                restarting = false
            }
        } label: {
            ZStack {
                Circle()
                    .fill(Color.white.opacity(0.85))
                    .frame(width: 32, height: 32)
                    .overlay(Circle().strokeBorder(Color.white, lineWidth: 1))
                if restarting {
                    ProgressView().scaleEffect(0.55)
                } else {
                    Image(systemName: "arrow.clockwise")
                        .foregroundStyle(Resona.Palette.inkSoft)
                        .font(.system(size: 14, weight: .semibold))
                }
            }
        }
        .buttonStyle(.plain)
        .disabled(restarting)
        .help("Restart signal — reconnects the Muse pipeline if it's stuck.")
    }

    private var restartIconButton: some View {
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
            .resonaPill(active: false, tint: Resona.Palette.peach)
        }
        .buttonStyle(.plain)
        .disabled(restarting)
        .help("Restart signal — reconnects the Muse pipeline if it's stuck.")
    }

    // MARK: stuck banner

    private var stuckBanner: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.arrow.triangle.2.circlepath")
                .font(.title2)
                .foregroundStyle(Resona.Palette.coral)
            VStack(alignment: .leading, spacing: 2) {
                Text("Signal stuck")
                    .font(Resona.Typography.headline)
                    .foregroundStyle(Resona.Palette.ink)
                Text(String(
                    format: "No fresh frames for %.0f s. Restart to reconnect the Muse.",
                    frameAgeSeconds ?? 0
                ))
                .font(Resona.Typography.caption)
                .foregroundStyle(Resona.Palette.inkSoft)
            }
            Spacer()
            restartIconButton
        }
        .resonaCard(tint: Resona.Palette.coral.opacity(0.18))
    }

    // MARK: quick stats

    /// Fixed card height for the stats and footer grids — chosen to fit
    /// the tallest content (sticker + 3 text lines) so every card looks
    /// identical regardless of how much its body has to say.
    private let cardHeight: CGFloat = 132

    private var quickStats: some View {
        let cols = Array(repeating: GridItem(.flexible(), spacing: 12), count: 4)
        return LazyVGrid(columns: cols, alignment: .leading, spacing: 12) {
            StickerStateCard(
                title: "Focus (frontal)",
                value: client.latestFrame?.frontalFocusEma.map { String(format: "%.2f", $0) } ?? "—",
                icon: "sun.max.fill",
                tint: Resona.Palette.coral,
                subtitle: "β / α · smoothed"
            )
            .frame(height: cardHeight)
            StickerStateCard(
                title: "Current state",
                value: client.latestFrame?.label ?? "—",
                icon: "sparkles",
                tint: Resona.Palette.lavender,
                subtitle: client.verdict?.tone.capitalized
            )
            .frame(height: cardHeight)
            StickerStateCard(
                title: client.gatekeeper?.quiet == true ? "Quiet ON" : "Quiet OFF",
                value: client.gatekeeper.map { "\($0.queuedCount) held" } ?? "—",
                icon: "moon.zzz.fill",
                tint: client.gatekeeper?.quiet == true ? Resona.Palette.sky : Resona.Palette.mint,
                subtitle: client.gatekeeper?.quiet == true ? "Notifications paused" : "Pings flowing"
            )
            .frame(height: cardHeight)
            StickerStateCard(
                title: "Total time",
                value: totalTimeText,
                icon: "clock.fill",
                tint: Resona.Palette.apricot,
                subtitle: "this session"
            )
            .frame(height: cardHeight)
        }
    }

    private var totalTimeText: String {
        guard let s = client.activeSession else { return "—" }
        let live = max(0, Date().timeIntervalSince1970 - s.startedAt)
        let secs = Int(max(live, s.summary.durationS))
        let m = secs / 60
        if m < 60 { return "\(m)m" }
        return String(format: "%dh %02dm", m / 60, m % 60)
    }

    // MARK: skeptic chip — only surfaces when caution flag is hot

    @ViewBuilder
    private var skepticChip: some View {
        if let s = client.appraisal, s.caution {
            HStack(spacing: 10) {
                Image(systemName: "exclamationmark.bubble.fill")
                    .foregroundStyle(Resona.Palette.coral)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Skeptic: caution")
                        .font(Resona.Typography.headline)
                        .foregroundStyle(Resona.Palette.ink)
                    Text("Recent reward burst — agents will probe instead of affirm.")
                        .font(Resona.Typography.caption)
                        .foregroundStyle(Resona.Palette.inkSoft)
                }
                Spacer()
            }
            .resonaCard(tint: Resona.Palette.butter.opacity(0.5))
        }
    }

    // MARK: coach panel — inline LLM Q&A (merged from old Coach tab)

    private var coachPanel: some View {
        DisclosureGroup(isExpanded: $showCoach) {
            CoachInline()
                .padding(.top, 8)
        } label: {
            HStack(spacing: 10) {
                CoachOrb(size: 22)
                Text("Ask the Coach")
                    .font(Resona.Typography.headline)
                    .foregroundStyle(Resona.Palette.ink)
                if !client.llmAvailable {
                    Text("offline")
                        .font(.caption2)
                        .padding(.horizontal, 8).padding(.vertical, 2)
                        .background(Capsule().fill(Resona.Palette.coral.opacity(0.25)))
                        .foregroundStyle(Resona.Palette.coral)
                }
            }
        }
        .resonaCard(tint: Resona.Palette.lilac.opacity(0.35))
    }

    // MARK: footer — privacy + Muse-2 + daily-goal donut, mockup-style

    private var footerStrip: some View {
        let cols = Array(repeating: GridItem(.flexible(), spacing: 12), count: 3)
        return LazyVGrid(columns: cols, alignment: .leading, spacing: 12) {
            PrivacyMusePill()
                .frame(height: cardHeight)
            MuseDevicePill(
                connected: client.battery?.stale == false,
                batteryPct: client.battery?.batteryPct
            )
            .frame(height: cardHeight)
            DailyQuestCard(
                minutesToday: focusedMinutesToday,
                goalMinutes: dailyGoalMinutes
            )
            .frame(height: cardHeight)
        }
    }

    /// Daily focus goal in minutes. 60 by default — the design-system
    /// "Daily quest 72%" example assumes a one-hour daily target.
    private let dailyGoalMinutes: Int = 60

    /// Minutes of EEG recording captured today, summed across all sessions
    /// whose `startedAt` falls within the user's local day plus the live
    /// active session. Unlike a raw frame counter this updates as the day
    /// rolls over, so the donut resets each morning.
    private var focusedMinutesToday: Double {
        let cal = Calendar.current
        let startOfDay = cal.startOfDay(for: Date()).timeIntervalSince1970

        // Past sessions today
        let pastSeconds = client.sessions
            .filter { $0.startedAt >= startOfDay }
            .reduce(0.0) { $0 + $1.summary.durationS }

        // Active session, if any — duration since startedAt or the
        // session-summary durationS, whichever is greater (live timer).
        let activeSeconds: Double = {
            guard let s = client.activeSession else { return 0 }
            let live = max(0, Date().timeIntervalSince1970 - s.startedAt)
            return max(live, s.summary.durationS)
        }()

        return (pastSeconds + activeSeconds) / 60.0
    }

    // MARK: signal detail

    private var signalDetail: some View {
        DisclosureGroup(isExpanded: $showDetails) {
            VStack(alignment: .leading, spacing: 12) {
                if let q = client.signalQuality?.signalQuality {
                    SignalQualityRow(quality: q)
                }
                ArtifactBanner(frame: client.latestFrame)
                BandPreviewRow(frame: client.latestFrame)
            }
            .padding(.top, 8)
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "waveform.path")
                    .foregroundStyle(Resona.Palette.sky)
                Text("Show signal detail")
                    .font(Resona.Typography.headline)
                    .foregroundStyle(Resona.Palette.ink)
            }
        }
        .resonaCard(tint: Resona.Palette.mist)
    }
}

// MARK: BandPreviewRow + BandBar — restyled with palette

struct BandPreviewRow: View {
    let frame: FocusFrame?

    private let bands: [(String, ClosedRange<Double>, KeyPath<FocusFrame, Double?>, String, Color)] = [
        ("δ delta", 15...35, \.deltaRel, "deep sleep / drowsy lapses", Resona.Palette.lavender),
        ("θ theta", 10...25, \.thetaRel, "drifting / flow / drowsy",   Resona.Palette.lilac),
        ("α alpha", 15...35, \.alphaRel, "relaxed wakeful",             Resona.Palette.sky),
        ("β beta",  10...30, \.betaRel,  "alert / engaged",             Resona.Palette.mint),
        ("γ gamma",  5...20, \.gammaRel, "binding / 'aha' (noisy)",     Resona.Palette.peach),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Band power")
                    .font(Resona.Typography.headline)
                    .foregroundStyle(Resona.Palette.ink)
                Spacer()
                Text("% of total · gray ticks = typical range")
                    .font(.caption2).foregroundStyle(Resona.Palette.inkFaint)
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
    let refRange: ClosedRange<Double>
    let relativePct: Double?

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 8) {
                Text(label)
                    .font(.callout.monospaced())
                    .frame(width: 70, alignment: .leading)
                    .foregroundStyle(color)
                Text(hint).font(.caption).foregroundStyle(Resona.Palette.inkFaint)
                Spacer()
                Text(relativePct.map { String(format: "%.0f%%", $0) } ?? "—")
                    .font(.callout.monospaced())
                    .foregroundStyle(Resona.Palette.ink)
                    .frame(width: 50, alignment: .trailing)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.white.opacity(0.6))
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Resona.Palette.inkFaint.opacity(0.25))
                        .frame(
                            width: geo.size.width * (refRange.upperBound - refRange.lowerBound) / 100,
                            height: 6
                        )
                        .offset(x: geo.size.width * refRange.lowerBound / 100)
                    if let pct = relativePct {
                        let clamped = max(0, min(100, pct))
                        RoundedRectangle(cornerRadius: 4)
                            .fill(color)
                            .frame(width: geo.size.width * clamped / 100, height: 8)
                    }
                }
            }
            .frame(height: 8)
        }
    }
}

// MARK: BatteryPill — pastel restyle

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
        guard let p = pct, !stale else { return Resona.Palette.inkFaint }
        if p < 15 { return Resona.Palette.coral }
        if p < 30 { return Resona.Palette.peach }
        return Resona.Palette.focus
    }

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon).foregroundStyle(tint)
            Text(pct.map { String(format: "%.0f%%", $0) } ?? "—")
                .font(.callout.monospacedDigit())
                .foregroundStyle(stale ? Resona.Palette.inkFaint : Resona.Palette.ink)
        }
        .padding(.horizontal, 12).padding(.vertical, 6)
        .background(Capsule().fill(Color.white.opacity(0.7)))
        .overlay(Capsule().strokeBorder(Color.white, lineWidth: 1))
        .help(stale
              ? "Headband battery: no recent telemetry."
              : "Muse headband battery.")
    }
}

// MARK: CoachInline — compact chat panel pulled out of the old CoachView

struct CoachInline: View {
    @EnvironmentObject var client: NaoClient
    @State private var messages: [NaoClient.ChatMsg] = []
    @State private var draft: String = ""
    @State private var pending: Bool = false
    @State private var selectedModel: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if !client.llmAvailable {
                installHint
            } else {
                if !client.llmModels.isEmpty {
                    HStack {
                        Text("Model")
                            .font(Resona.Typography.caption)
                            .foregroundStyle(Resona.Palette.inkSoft)
                        Picker("", selection: $selectedModel) {
                            ForEach(client.llmModels, id: \.self) { m in
                                Text(m).tag(m)
                            }
                        }
                        .pickerStyle(.menu)
                        .labelsHidden()
                        .frame(maxWidth: 220)
                        .onAppear {
                            if selectedModel.isEmpty, let first = client.llmModels.first {
                                selectedModel = first
                            }
                        }
                        Spacer()
                        Button("Reset") { messages.removeAll() }
                            .buttonStyle(.plain)
                            .font(Resona.Typography.caption)
                            .foregroundStyle(Resona.Palette.lavender)
                    }
                }
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(messages) { m in
                                ChatBubble(message: m).id(m.id)
                            }
                            if pending {
                                HStack(spacing: 6) {
                                    ProgressView().controlSize(.small)
                                    Text("Thinking…")
                                        .font(Resona.Typography.caption)
                                        .foregroundStyle(Resona.Palette.inkSoft)
                                }
                            }
                        }
                        .padding(.vertical, 6)
                    }
                    .frame(maxHeight: 220)
                    .onChange(of: messages.count) { _, _ in
                        if let last = messages.last {
                            withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                        }
                    }
                }
                inputBar
            }
        }
    }

    private var installHint: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Local LLM not running", systemImage: "exclamationmark.triangle")
                .font(Resona.Typography.headline)
                .foregroundStyle(Resona.Palette.coral)
            Text("Install Ollama and pull a small model:")
                .font(Resona.Typography.caption)
                .foregroundStyle(Resona.Palette.inkSoft)
            Text("brew install ollama").font(.system(.caption, design: .monospaced))
            Text("ollama serve").font(.system(.caption, design: .monospaced))
            Text("ollama pull llama3.2:3b").font(.system(.caption, design: .monospaced))
            Button("Refresh") { Task { await client.loadLLMHealth() } }
                .buttonStyle(.plain)
                .font(Resona.Typography.pill)
                .padding(.horizontal, 10).padding(.vertical, 4)
                .background(Capsule().fill(Resona.Palette.lavender.opacity(0.5)))
        }
    }

    private var inputBar: some View {
        HStack(alignment: .bottom, spacing: 8) {
            TextEditor(text: $draft)
                .frame(minHeight: 36, maxHeight: 80)
                .scrollContentBackground(.hidden)
                .padding(8)
                .background(
                    RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.7))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .strokeBorder(Resona.Palette.lavender.opacity(0.5), lineWidth: 1)
                )
            Button {
                Task { await send() }
            } label: {
                Image(systemName: "paperplane.fill")
                    .padding(10)
                    .background(Circle().fill(Resona.Palette.peach))
                    .foregroundStyle(.white)
            }
            .buttonStyle(.plain)
            .keyboardShortcut(.return, modifiers: [.command])
            .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || pending)
        }
    }

    private func send() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        let userMsg = NaoClient.ChatMsg(role: "user", content: text)
        messages.append(userMsg)
        draft = ""
        pending = true
        do {
            let reply = try await client.chat(
                messages: messages,
                model: selectedModel.isEmpty ? nil : selectedModel
            )
            messages.append(NaoClient.ChatMsg(role: "assistant", content: reply))
        } catch {
            messages.append(NaoClient.ChatMsg(
                role: "assistant",
                content: "Error: \(error.localizedDescription)"
            ))
        }
        pending = false
    }
}
