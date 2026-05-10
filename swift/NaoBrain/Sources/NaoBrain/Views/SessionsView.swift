import Charts
import SwiftUI

/// Top-level Sessions tab. NavigationSplitView so the list of past sessions
/// stays visible on macOS while the detail (chart + insights + chat) opens
/// on the right.
struct SessionsView: View {
    @EnvironmentObject var client: NaoClient
    @State private var selectedId: String?

    var body: some View {
        NavigationSplitView {
            sessionList
                .frame(minWidth: 240)
        } detail: {
            if let id = selectedId,
               let s = client.sessions.first(where: { $0.id == id }) {
                SessionDetailView(session: s)
                    .id(id)  // re-init detail when switching sessions
            } else {
                ContentUnavailableView(
                    "Pick a session",
                    systemImage: "waveform.path.ecg",
                    description: Text("Past recordings live in ~/.nao/sessions. Start a new one from the Now tab.")
                )
            }
        }
        .task { await client.loadSessions() }
    }

    private var sessionList: some View {
        List(selection: $selectedId) {
            if client.sessions.isEmpty {
                Text("No sessions yet.")
                    .foregroundStyle(.secondary)
            }
            ForEach(client.sessions) { s in
                SessionRow(session: s)
                    .tag(s.id)
                    .contextMenu {
                        Button("Delete", role: .destructive) {
                            Task {
                                await client.deleteSession(s.id)
                                if selectedId == s.id { selectedId = nil }
                            }
                        }
                    }
            }
        }
        .listStyle(.sidebar)
        .refreshable { await client.loadSessions() }
    }
}

// MARK: row

private struct SessionRow: View {
    let session: Session
    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(session.label)
                    .font(.headline)
                Spacer()
                Text(durationLabel(session.summary.durationS))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            HStack(spacing: 8) {
                if let f = session.summary.focusMean {
                    Tag(text: String(format: "F %.2f", f), tint: .blue)
                }
                if let a = session.summary.asymmetryMean {
                    Tag(text: String(format: "asym %+.2f", a), tint: .purple)
                }
                if session.summary.artifactRate > 0.2 {
                    Tag(text: "noisy", tint: .orange)
                }
            }
            .font(.caption)
            Text(startedLabel(session.startedAt))
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }

    private func startedLabel(_ epoch: Double) -> String {
        let fmt = DateFormatter()
        fmt.dateStyle = .medium
        fmt.timeStyle = .short
        return fmt.string(from: Date(timeIntervalSince1970: epoch))
    }

    private func durationLabel(_ s: Double) -> String {
        if s < 60 { return String(format: "%.0fs", s) }
        if s < 3600 {
            let m = Int(s) / 60
            let r = Int(s) % 60
            return "\(m)m\(r)s"
        }
        let h = Int(s) / 3600
        let m = (Int(s) % 3600) / 60
        return "\(h)h\(m)m"
    }
}

private struct Tag: View {
    let text: String
    let tint: Color
    var body: some View {
        Text(text)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(tint.opacity(0.15), in: Capsule())
            .foregroundStyle(tint)
    }
}

// MARK: detail

struct SessionDetailView: View {
    @EnvironmentObject var client: NaoClient
    let session: Session

    @State private var frames: [NaoClient.SessionFramePoint] = []
    @State private var insights: NaoClient.SessionInsights?
    @State private var loading: Bool = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                header
                summaryCards
                if !frames.isEmpty {
                    focusChart
                    asymmetryChart
                } else if loading {
                    HStack {
                        ProgressView().controlSize(.small)
                        Text("Loading frames…").foregroundStyle(.secondary)
                    }
                }
                if let ins = insights {
                    insightsBlock(ins)
                }
                Divider().padding(.vertical, 4)
                SessionChatPanel(session: session)
            }
            .padding()
        }
        .task(id: session.id) { await loadAll() }
    }

    private func loadAll() async {
        loading = true
        async let fs = client.loadSessionFrames(session.id, step: 1)
        async let ins = client.loadSessionInsights(session.id)
        frames = await fs
        insights = await ins
        loading = false
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 2) {
                Text(session.label)
                    .font(.title2.weight(.semibold))
                Text(headerSubtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
    }

    private var headerSubtitle: String {
        let dur = session.summary.durationS
        let durStr: String
        if dur < 60 { durStr = String(format: "%.0fs", dur) }
        else if dur < 3600 { durStr = String(format: "%.1f min", dur / 60.0) }
        else { durStr = String(format: "%.2f h", dur / 3600.0) }
        let dt = Date(timeIntervalSince1970: session.startedAt)
        let fmt = DateFormatter(); fmt.dateStyle = .medium; fmt.timeStyle = .short
        return "\(fmt.string(from: dt)) · \(durStr) · \(session.summary.frameCount) frames"
    }

    private var summaryCards: some View {
        HStack(spacing: 10) {
            MetricCard(
                title: "focus mean",
                value: session.summary.focusMean.map { String(format: "%.2f", $0) } ?? "—"
            )
            MetricCard(
                title: "focus std",
                value: session.summary.focusStd.map { String(format: "%.2f", $0) } ?? "—"
            )
            MetricCard(
                title: "asymmetry",
                value: session.summary.asymmetryMean.map { String(format: "%+.2f", $0) } ?? "—"
            )
            MetricCard(
                title: "artifact rate",
                value: String(format: "%.0f%%", session.summary.artifactRate * 100),
                tint: session.summary.artifactRate > 0.2 ? .orange : .secondary
            )
        }
    }

    private var focusChart: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Focus over session")
                .font(.headline)
            Chart {
                ForEach(frames) { f in
                    LineMark(
                        x: .value("min", relMinutes(f.ts)),
                        y: .value("focus", f.focusEma)
                    )
                    .interpolationMethod(.monotone)
                    .foregroundStyle(.blue)
                }
                if let drop = insights?.biggestDrop {
                    PointMark(
                        x: .value("min", drop.tMinute),
                        y: .value("focus", drop.focusMean)
                    )
                    .foregroundStyle(.red)
                    .symbolSize(80)
                    .annotation(position: .top) {
                        Text("low")
                            .font(.caption2)
                            .foregroundStyle(.red)
                    }
                }
            }
            .chartXAxisLabel("minutes")
            .frame(height: 200)
        }
    }

    private var asymmetryChart: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Frontal alpha asymmetry")
                    .font(.headline)
                Text("(left = withdrawal, right = approach)")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Chart {
                ForEach(frames) { f in
                    if let a = f.frontalAsymmetry {
                        LineMark(
                            x: .value("min", relMinutes(f.ts)),
                            y: .value("asym", a)
                        )
                        .foregroundStyle(.purple)
                        .interpolationMethod(.monotone)
                    }
                }
                RuleMark(y: .value("zero", 0))
                    .foregroundStyle(.gray.opacity(0.5))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))
            }
            .frame(height: 140)
        }
    }

    private func insightsBlock(_ ins: NaoClient.SessionInsights) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Insights")
                .font(.headline)
            HStack(spacing: 14) {
                if let slope = ins.trendSlopePerMin {
                    KV(k: "trend / min", v: String(format: "%+.3f", slope))
                }
                if let drop = ins.biggestDrop {
                    KV(
                        k: "biggest drop",
                        v: String(format: "%.2f at %.1f min", drop.focusMean, drop.tMinute)
                    )
                }
            }
            .font(.callout)

            HStack(spacing: 14) {
                Text("quartiles:").foregroundStyle(.secondary).font(.caption)
                quartileChip("Q1", ins.quartiles.q1)
                quartileChip("Q2", ins.quartiles.q2)
                quartileChip("Q3", ins.quartiles.q3)
                quartileChip("Q4", ins.quartiles.q4)
            }

            if let vc = ins.vsCalibration {
                HStack(spacing: 8) {
                    Image(systemName: "person.fill")
                    Text(String(format: "vs your baseline: z = %.2f", vc.zScore))
                        .font(.callout)
                }.foregroundStyle(.secondary)
            }
            if let vlb = ins.vsLabelBaseline, let d = vlb.delta {
                let arrow = d > 0 ? "↑" : "↓"
                HStack(spacing: 8) {
                    Image(systemName: "chart.bar")
                    Text(String(
                        format: "vs %d prior %@ session(s): %@ %.2f",
                        vlb.nPrior, vlb.label, arrow, abs(d)
                    ))
                    .font(.callout)
                }.foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 10))
    }

    private func quartileChip(_ name: String, _ v: Double?) -> some View {
        HStack(spacing: 4) {
            Text(name).foregroundStyle(.secondary)
            Text(v.map { String(format: "%.2f", $0) } ?? "—")
                .monospacedDigit()
        }
        .font(.caption)
        .padding(.horizontal, 6).padding(.vertical, 2)
        .background(Color.blue.opacity(0.10), in: Capsule())
    }

    private func relMinutes(_ ts: Double) -> Double {
        let t0 = frames.first?.ts ?? ts
        return (ts - t0) / 60.0
    }
}

private struct KV: View {
    let k: String; let v: String
    var body: some View {
        HStack(spacing: 4) {
            Text(k).foregroundStyle(.secondary)
            Text(v).fontWeight(.semibold).monospacedDigit()
        }
    }
}

// MARK: chat

private struct SessionChatPanel: View {
    @EnvironmentObject var client: NaoClient
    let session: Session
    @State private var messages: [NaoClient.ChatMsg] = []
    @State private var draft: String = ""
    @State private var pending: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: "bubble.left.and.bubble.right")
                Text("Ask the Coach about this session")
                    .font(.headline)
                Spacer()
                if !messages.isEmpty {
                    Button("Reset") { messages.removeAll() }
                        .buttonStyle(.borderless)
                        .font(.caption)
                }
            }

            if !client.llmAvailable {
                Label("Local LLM unavailable. Ollama must be running.", systemImage: "exclamationmark.triangle")
                    .font(.callout)
                    .foregroundStyle(.orange)
            } else {
                if messages.isEmpty {
                    suggestionChips
                }
                ForEach(messages) { m in
                    chatBubble(m)
                }
                if pending {
                    HStack {
                        ProgressView().controlSize(.small)
                        Text("Thinking…").font(.caption).foregroundStyle(.secondary)
                    }
                }
                input
            }
        }
        .padding(12)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 10))
    }

    private var suggestionChips: some View {
        let suggestions = [
            "Where did I lose focus during this session?",
            "How did this compare to my other \(session.label) sessions?",
            "What practical takeaway should I act on?",
            "Was my brain calmer or more activated than usual?",
        ]
        return FlowRow {
            ForEach(suggestions, id: \.self) { s in
                Button(s) { Task { await send(prompt: s) } }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
            }
        }
    }

    private func chatBubble(_ m: NaoClient.ChatMsg) -> some View {
        HStack {
            if m.role == "user" { Spacer(minLength: 40) }
            Text(m.content)
                .padding(8)
                .background(
                    (m.role == "user" ? Color.accentColor.opacity(0.15) : Color.gray.opacity(0.10)),
                    in: RoundedRectangle(cornerRadius: 8)
                )
                .frame(maxWidth: 600, alignment: m.role == "user" ? .trailing : .leading)
            if m.role != "user" { Spacer(minLength: 40) }
        }
    }

    private var input: some View {
        HStack(alignment: .bottom) {
            TextEditor(text: $draft)
                .frame(minHeight: 36, maxHeight: 90)
                .scrollContentBackground(.hidden)
                .padding(6)
                .background(Color.gray.opacity(0.08), in: RoundedRectangle(cornerRadius: 6))
            Button("Send") { Task { await send(prompt: nil) } }
                .keyboardShortcut(.return, modifiers: [.command])
                .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || pending)
        }
    }

    private func send(prompt: String?) async {
        let text = prompt ?? draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        if prompt == nil { draft = "" }
        let userMsg = NaoClient.ChatMsg(role: "user", content: text)
        messages.append(userMsg)
        pending = true
        do {
            let reply = try await client.sessionChat(session.id, messages: messages)
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

/// Tiny FlowLayout shim — wraps suggestion chips that don't fit on one line.
private struct FlowRow<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 6) { content }
            VStack(alignment: .leading, spacing: 6) { content }
        }
    }
}
