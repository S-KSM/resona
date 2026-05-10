import SwiftUI

struct CoachView: View {
    @EnvironmentObject var client: NaoClient

    @State private var messages: [NaoClient.ChatMsg] = []
    @State private var draft: String = ""
    @State private var pending: Bool = false
    @State private var selectedModel: String = ""

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()

            if !client.llmAvailable {
                installHint
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(messages) { m in
                                ChatBubble(message: m)
                                    .id(m.id)
                            }
                            if pending {
                                HStack {
                                    ProgressView().controlSize(.small)
                                    Text("Thinking…").foregroundStyle(.secondary).font(.caption)
                                }
                            }
                        }
                        .padding()
                    }
                    .onChange(of: messages.count) { _, _ in
                        if let last = messages.last {
                            withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                        }
                    }
                }

                Divider()
                inputBar
            }
        }
    }

    private var header: some View {
        HStack {
            Text("Coach")
                .font(.headline)
            Spacer()
            if !client.llmModels.isEmpty {
                Picker("Model", selection: $selectedModel) {
                    ForEach(client.llmModels, id: \.self) { m in
                        Text(m).tag(m)
                    }
                }
                .pickerStyle(.menu)
                .frame(maxWidth: 260)
                .onAppear {
                    if selectedModel.isEmpty, let first = client.llmModels.first {
                        selectedModel = first
                    }
                }
            }
            Button("Reset chat") { messages.removeAll() }
                .buttonStyle(.borderless)
        }
        .padding(.horizontal).padding(.vertical, 10)
    }

    private var installHint: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Local LLM not running", systemImage: "exclamationmark.triangle")
                .font(.headline)
            Text("Install Ollama and pull a small model:")
                .foregroundStyle(.secondary)
            Text("brew install ollama").font(.system(.body, design: .monospaced))
            Text("ollama serve").font(.system(.body, design: .monospaced))
            Text("ollama pull llama3.2:3b").font(.system(.body, design: .monospaced))
            Text("Then click Refresh.")
            Button("Refresh") { Task { await client.loadLLMHealth() } }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
        .padding()
    }

    private var inputBar: some View {
        HStack(alignment: .bottom) {
            TextEditor(text: $draft)
                .frame(minHeight: 40, maxHeight: 100)
                .scrollContentBackground(.hidden)
                .padding(8)
                .background(Color.gray.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))

            Button("Send") { Task { await send() } }
                .keyboardShortcut(.return, modifiers: [.command])
                .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || pending)
        }
        .padding()
    }

    private func send() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        let userMsg = NaoClient.ChatMsg(role: "user", content: text)
        messages.append(userMsg)
        draft = ""
        pending = true
        do {
            let reply = try await client.chat(messages: messages, model: selectedModel.isEmpty ? nil : selectedModel)
            messages.append(NaoClient.ChatMsg(role: "assistant", content: reply))
        } catch {
            messages.append(NaoClient.ChatMsg(role: "assistant", content: "Error: \(error.localizedDescription)"))
        }
        pending = false
    }
}

struct ChatBubble: View {
    let message: NaoClient.ChatMsg
    var body: some View {
        HStack {
            if message.role == "user" { Spacer(minLength: 40) }
            Text(message.content)
                .padding(10)
                .background(
                    (message.role == "user" ? Color.accentColor.opacity(0.15) : Color.gray.opacity(0.12)),
                    in: RoundedRectangle(cornerRadius: 10)
                )
                .frame(maxWidth: 600, alignment: message.role == "user" ? .trailing : .leading)
            if message.role != "user" { Spacer(minLength: 40) }
        }
    }
}
