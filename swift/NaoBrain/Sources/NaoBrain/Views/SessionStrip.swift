import SwiftUI

/// Compact header strip on the Live tab. Idle: "Start session" button + label
/// picker. Recording: red dot + label + duration + frame count + Stop.
struct SessionStrip: View {
    @EnvironmentObject var client: NaoClient
    @State private var pickerOpen: Bool = false
    @State private var draftLabel: String = SessionLabelSuggestion.deepWork.rawValue
    @State private var customLabel: String = ""
    @State private var notes: String = ""
    @State private var now: Date = Date()

    private let timer = Timer.publish(every: 1.0, on: .main, in: .common).autoconnect()

    var body: some View {
        Group {
            if let s = client.activeSession {
                recording(session: s)
            } else {
                idle
            }
        }
        .padding(10)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 10))
        .onReceive(timer) { now = $0 }
    }

    // MARK: idle

    private var idle: some View {
        HStack(spacing: 12) {
            Image(systemName: "record.circle")
                .foregroundStyle(.secondary)
            Text("No session recording")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
            Button {
                pickerOpen = true
            } label: {
                Label("Start session", systemImage: "play.fill")
            }
            .buttonStyle(.borderedProminent)
        }
        .popover(isPresented: $pickerOpen, arrowEdge: .top) {
            startPicker
                .padding()
                .frame(width: 320)
        }
    }

    private var startPicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Label this session").font(.headline)
            Picker("Label", selection: $draftLabel) {
                ForEach(SessionLabelSuggestion.allCases) { s in
                    Text(s.display).tag(s.rawValue)
                }
                Text("custom…").tag("__custom__")
            }
            .pickerStyle(.menu)

            if draftLabel == "__custom__" {
                TextField("custom label", text: $customLabel)
                    .textFieldStyle(.roundedBorder)
            }

            Text("Notes (optional)").font(.caption).foregroundStyle(.secondary)
            TextEditor(text: $notes)
                .frame(minHeight: 60, maxHeight: 100)
                .scrollContentBackground(.hidden)
                .padding(6)
                .background(Color.gray.opacity(0.08), in: RoundedRectangle(cornerRadius: 6))

            HStack {
                Spacer()
                Button("Cancel") { pickerOpen = false }
                Button("Start") {
                    let label = (draftLabel == "__custom__")
                        ? customLabel.trimmingCharacters(in: .whitespacesAndNewlines)
                        : draftLabel
                    guard !label.isEmpty else { return }
                    pickerOpen = false
                    Task {
                        await client.startSession(label: label, notes: notes)
                        notes = ""
                        customLabel = ""
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(
                    draftLabel == "__custom__"
                    && customLabel.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                )
            }
        }
    }

    // MARK: recording

    private func recording(session s: Session) -> some View {
        HStack(spacing: 10) {
            Circle()
                .fill(.red)
                .frame(width: 10, height: 10)
                .opacity(blinkOpacity)
            Text("Recording")
                .font(.subheadline.weight(.semibold))
            Text(s.label)
                .font(.subheadline)
                .padding(.horizontal, 6).padding(.vertical, 2)
                .background(Color.accentColor.opacity(0.15), in: Capsule())
            Text(durationString(s))
                .font(.system(.subheadline, design: .monospaced))
                .foregroundStyle(.secondary)
            Text("· \(s.summary.frameCount) frames")
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
            Button(role: .destructive) {
                Task { await client.stopSession() }
            } label: {
                Label("Stop", systemImage: "stop.fill")
            }
            .buttonStyle(.bordered)
        }
    }

    private var blinkOpacity: Double {
        // 1 Hz pulse without animations to avoid jank inside ScrollView.
        Int(now.timeIntervalSince1970) % 2 == 0 ? 1.0 : 0.4
    }

    private func durationString(_ s: Session) -> String {
        let elapsed = max(0, now.timeIntervalSince1970 - s.startedAt)
        let h = Int(elapsed) / 3600
        let m = (Int(elapsed) % 3600) / 60
        let sec = Int(elapsed) % 60
        if h > 0 {
            return String(format: "%d:%02d:%02d", h, m, sec)
        }
        return String(format: "%02d:%02d", m, sec)
    }
}
