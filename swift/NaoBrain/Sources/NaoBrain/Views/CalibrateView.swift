import AVFoundation
import SwiftUI

struct CalibrateView: View {
    @EnvironmentObject var client: NaoClient

    @State private var secondsPerPhase: Double = 60
    @State private var prose: String = ""
    @State private var prosePending = false
    @State private var lastSpokenPhase: String = ""

    private let speech = SpeechService.shared

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Calibrate")
                    .font(.title)
                Text("Two-phase recording (eyes open + eyes closed). Voice guides you. F values get z-scored against your personal baseline so labels become accurate.")
                    .foregroundStyle(.secondary)
                    .font(.callout)

                if !isRunning {
                    SignalQualityCard()
                }

                if let progress = client.calibrationProgress {
                    runningCard(progress: progress)
                } else {
                    startCard
                }
            }
            .padding()
        }
        .onChange(of: client.calibrationProgress?.phase) { _, newPhase in
            handlePhaseChange(newPhase)
        }
    }

    // MARK: Sub-views

    private var startCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let cal = client.calibration {
                baselineSummary(cal)
            }
            HStack {
                Text("Seconds per phase").bold()
                Slider(value: $secondsPerPhase, in: 30...120, step: 10)
                Text("\(Int(secondsPerPhase))s").monospacedDigit()
            }
            HStack {
                Button("Start calibration") {
                    Task { await startSequence() }
                }
                .keyboardShortcut(.return, modifiers: [])
                .buttonStyle(.borderedProminent)
                Spacer()
            }
            Text("Sit still. Headband centered. Don't clench jaw. ~2 minutes.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    @ViewBuilder
    private func baselineSummary(_ cal: CalibrationResult) -> some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Last baseline").font(.caption.bold())
                Text("mean F \(String(format: "%.3f", cal.meanF)) · n=\(cal.nSamples)")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            baselineAgeBadge(cal)
        }
    }

    @ViewBuilder
    private func baselineAgeBadge(_ cal: CalibrationResult) -> some View {
        if let age = cal.ageDays {
            let stale = cal.isStale ?? (age > 7)
            HStack(spacing: 4) {
                Image(systemName: stale ? "exclamationmark.triangle.fill" : "clock")
                Text(ageDescription(age))
                    .font(.caption.monospacedDigit())
                if stale {
                    Text("· stale, re-calibrate").font(.caption)
                }
            }
            .foregroundStyle(stale ? .orange : .secondary)
        } else {
            Label("Age unknown — pre-drift baseline", systemImage: "questionmark.circle")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private func ageDescription(_ days: Double) -> String {
        if days < 1 {
            let hours = max(1, Int(days * 24))
            return "\(hours)h old"
        }
        return "\(Int(days.rounded())) day\(days >= 1.5 ? "s" : "") old"
    }

    private func runningCard(progress: CalibrationProgress) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                phaseChip(progress.phase)
                Spacer()
                Button("Cancel") {
                    Task { await client.cancelCalibration() }
                }
                .disabled(!progress.isRunning)

                Button("Reset") {
                    Task { await client.resetCalibration() }
                    lastSpokenPhase = ""
                    prose = ""
                }
            }

            if progress.isRunning,
               let remaining = progress.secondsRemaining,
               let total = progress.secondsTotal,
               total > 0 {
                ProgressView(value: 1 - (remaining / total)) {
                    Text(String(format: "%.1fs remaining", remaining))
                        .font(.caption).monospacedDigit()
                }
            }

            if progress.phase == "eyes_open", !prose.isEmpty {
                proseView
            }

            if progress.phase == "eyes_closed" {
                eyesClosedView
            }

            if progress.phase == "done", let result = progress.result {
                resultView(result, progress: progress)
            }

            if progress.phase == "error" {
                VStack(alignment: .leading, spacing: 8) {
                    Label(progress.error ?? "Unknown error", systemImage: "xmark.octagon")
                        .foregroundStyle(.red)
                    if let counts = progress.artifactCounts, !counts.isEmpty {
                        Text("Artifact breakdown:").font(.caption.bold())
                        ForEach(counts.sorted(by: { $0.key < $1.key }), id: \.key) { k, v in
                            Text("  \(k) = \(v)").font(.caption).monospaced()
                        }
                    }
                }
            }
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private var proseView: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Read aloud (or silently — just keep eyes on the text):")
                .font(.subheadline).foregroundStyle(.secondary)
            ScrollView {
                Text(prose)
                    .font(.system(.body, design: .serif))
                    .lineSpacing(6)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 200)
            .background(Color.gray.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
            if prosePending {
                ProgressView().controlSize(.small)
            }
        }
    }

    private var eyesClosedView: some View {
        VStack(spacing: 12) {
            Image(systemName: "eye.slash")
                .font(.system(size: 64))
                .foregroundStyle(.secondary)
            Text("Eyes closed. Relax.")
                .font(.title3)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
    }

    private func resultView(_ result: CalibrationResult, progress: CalibrationProgress) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Calibration saved.", systemImage: "checkmark.seal.fill")
                .foregroundStyle(.green)
                .font(.headline)
            HStack(spacing: 12) {
                MetricCard(title: "mean F", value: String(format: "%.3f", result.meanF))
                MetricCard(title: "std F",  value: String(format: "%.3f", result.stdF))
                MetricCard(title: "clean samples", value: "\(result.nSamples)")
            }
            if let counts = progress.artifactCounts {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Artifact summary").font(.caption.bold())
                    ForEach(counts.sorted(by: { $0.key < $1.key }), id: \.key) { k, v in
                        Text("\(k) = \(v)").font(.caption).monospaced()
                    }
                }
            }
        }
    }

    private func phaseChip(_ phase: String) -> some View {
        let label: String
        let color: Color
        switch phase {
        case "eyes_open":  label = "Eyes OPEN — read on screen";   color = .blue
        case "eyes_closed":label = "Eyes CLOSED — relax";          color = .indigo
        case "saving":     label = "Saving baseline…";             color = .orange
        case "done":       label = "Done";                         color = .green
        case "error":      label = "Error";                        color = .red
        case "idle":       label = "Idle";                         color = .secondary
        default:           label = phase;                          color = .secondary
        }
        return Text(label)
            .font(.headline)
            .foregroundStyle(color)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(color.opacity(0.15), in: Capsule())
    }

    // MARK: Voice + state machine

    private var isRunning: Bool {
        client.calibrationProgress?.isRunning == true
    }

    private func startSequence() async {
        prose = ""
        prosePending = true
        if let p = await client.calibrationProse() {
            prose = p
        }
        prosePending = false
        await client.startCalibration(secondsPerPhase: secondsPerPhase)
        speakIntro()
    }

    private func speakIntro() {
        speech.speak(
            "Calibration starting. Sit still and keep the headband centered. First phase, eyes open. Read the text on the screen, breathe normally. Beginning in three. Two. One. Begin.",
            voiceIdentifier: client.config?.voiceName,
            rate: voiceRate
        )
        lastSpokenPhase = "intro"
    }

    private func handlePhaseChange(_ newPhase: String?) {
        guard let phase = newPhase else { return }
        switch phase {
        case "eyes_closed":
            if lastSpokenPhase != "eyes_closed" {
                lastSpokenPhase = "eyes_closed"
                speech.speak(
                    "Eyes open phase complete. Now close your eyes and relax. Beginning in three. Two. One. Eyes closed.",
                    voiceIdentifier: client.config?.voiceName,
                    rate: voiceRate
                )
            }
        case "saving":
            if lastSpokenPhase != "saving" {
                lastSpokenPhase = "saving"
                speech.speak(
                    "Calibration complete. You may open your eyes. Saving baseline.",
                    voiceIdentifier: client.config?.voiceName,
                    rate: voiceRate
                )
            }
        case "error":
            speech.speak("Calibration error. Check the screen.", voiceIdentifier: client.config?.voiceName, rate: voiceRate)
        default:
            break
        }
    }

    private var voiceRate: Float {
        guard let raw = client.config?.voiceRate else { return 0.5 }
        return Float(raw) / 350.0
    }
}

struct SignalQualityCard: View {
    @EnvironmentObject var client: NaoClient
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Signal quality — preview before starting").font(.headline)
            if let q = client.signalQuality?.signalQuality {
                HStack(spacing: 12) {
                    ForEach(q) { c in ChannelQualityRow(quality: c) }
                }
                if let flags = client.signalQuality?.current?.artifactFlags, !flags.isEmpty {
                    Label("Currently flagged: " + flags.joined(separator: ", "),
                          systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange).font(.callout)
                    Text("Common fixes: BLINK = blink less; JAW = unclench; MOTION = hold still; BAD_CONTACT = reseat band.")
                        .font(.caption).foregroundStyle(.secondary)
                } else {
                    Label("Signal looks clean. Safe to start.", systemImage: "checkmark.seal")
                        .foregroundStyle(.green).font(.callout)
                }
            } else {
                Text("Buffer warming up…").font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}
