import AVFoundation
import SwiftUI

struct SetupView: View {
    @EnvironmentObject var client: NaoClient

    @State private var scanning = false
    @State private var scanResults: [MuseDevice] = []
    @State private var typedAddress: String = ""
    @State private var voiceIdentifier: String = ""
    @State private var voiceRate: Double = 0.5
    @State private var loadedConfigOnce = false
    @State private var sourceKind: String = "synthetic"

    private let speech = SpeechService.shared

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {

                section("Source") {
                    Picker("Stream", selection: $sourceKind) {
                        Text("Synthetic").tag("synthetic")
                        Text("Muse").tag("muse")
                    }
                    .pickerStyle(.segmented)
                    .frame(maxWidth: 320)
                    .onChange(of: sourceKind) { _, newValue in
                        Task {
                            await client.saveConfig(ConfigPatch(
                                museAddress: newValue == "synthetic" ? "" : nil,
                                voiceName: nil, voiceRate: nil,
                                lastSource: newValue
                            ))
                        }
                    }
                }

                section("Muse-14B3") {
                    if let saved = client.config?.museAddress, !saved.isEmpty {
                        Text("Saved: \(saved)").monospaced().font(.caption)
                    } else {
                        Text("No address saved.").font(.caption).foregroundStyle(.orange)
                    }

                    HStack {
                        Button(scanning ? "Scanning…" : "Scan (8 s)") {
                            Task {
                                scanning = true
                                scanResults = await client.scanMuse()
                                scanning = false
                            }
                        }
                        .disabled(scanning)

                        TextField("Override address", text: $typedAddress)
                            .textFieldStyle(.roundedBorder)
                            .frame(maxWidth: 320)

                        Button("Save typed") {
                            Task {
                                await client.saveConfig(ConfigPatch(
                                    museAddress: typedAddress.isEmpty ? nil : typedAddress,
                                    voiceName: nil, voiceRate: nil, lastSource: nil
                                ))
                                typedAddress = ""
                            }
                        }
                        .disabled(typedAddress.isEmpty)
                    }

                    if !scanResults.isEmpty {
                        VStack(alignment: .leading) {
                            ForEach(scanResults) { device in
                                HStack {
                                    Text(device.name).bold()
                                    Text(device.address).monospaced().font(.caption)
                                    Spacer()
                                    Button("Use") {
                                        Task {
                                            await client.saveConfig(ConfigPatch(
                                                museAddress: device.address,
                                                voiceName: nil, voiceRate: nil,
                                                lastSource: "muse"
                                            ))
                                        }
                                    }
                                }
                                .padding(.vertical, 4)
                            }
                        }
                        .padding(8)
                        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8))
                    }
                }

                section("Voice (AVSpeechSynthesizer, on-device)") {
                    Picker("Voice", selection: $voiceIdentifier) {
                        ForEach(SpeechService.availableVoices(), id: \.identifier) { v in
                            Text("\(v.name) · \(qualityLabel(v.quality))")
                                .tag(v.identifier)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: 380)

                    HStack {
                        Text("Rate")
                        Slider(value: $voiceRate, in: 0.3...0.7) { _ in }
                        Text(String(format: "%.2f", voiceRate)).monospacedDigit()
                    }

                    HStack {
                        Button("Test voice") {
                            speech.speak(
                                "This is the voice that will guide your calibration.",
                                voiceIdentifier: voiceIdentifier,
                                rate: Float(voiceRate)
                            )
                        }
                        Button("Save voice") {
                            Task {
                                await client.saveConfig(ConfigPatch(
                                    museAddress: nil,
                                    voiceName: voiceIdentifier,
                                    voiceRate: Int(voiceRate * 350),  // approx wpm
                                    lastSource: nil
                                ))
                            }
                        }
                    }
                    Text("Premium / Enhanced voices ship with macOS.")
                        .font(.caption).foregroundStyle(.secondary)
                }

                section("Calibration") {
                    if let cal = client.calibration {
                        HStack(spacing: 16) {
                            MetricCard(title: "mean F", value: String(format: "%.3f", cal.meanF))
                            MetricCard(title: "std F",  value: String(format: "%.3f", cal.stdF))
                            MetricCard(title: "samples", value: "\(cal.nSamples)")
                        }
                    } else {
                        Label("No baseline saved. Visit Calibrate.", systemImage: "exclamationmark.triangle")
                            .foregroundStyle(.orange)
                    }
                }

                Spacer()
            }
            .padding()
            .onAppear {
                if !loadedConfigOnce { applyLoadedConfig(); loadedConfigOnce = true }
            }
            .onChange(of: client.config) { _, _ in applyLoadedConfig() }
        }
    }

    private func applyLoadedConfig() {
        if let cfg = client.config {
            sourceKind = cfg.lastSource
            // voiceName field is a string identifier when set from AVSpeech.
            if !cfg.voiceName.isEmpty, AVSpeechSynthesisVoice(identifier: cfg.voiceName) != nil {
                voiceIdentifier = cfg.voiceName
            } else if voiceIdentifier.isEmpty,
                      let v = SpeechService.defaultVoice() {
                voiceIdentifier = v.identifier
            }
            voiceRate = Double(cfg.voiceRate) / 350.0
        }
    }

    private func qualityLabel(_ q: AVSpeechSynthesisVoiceQuality) -> String {
        switch q {
        case .premium:  return "Premium"
        case .enhanced: return "Enhanced"
        default:        return "Default"
        }
    }

    @ViewBuilder
    private func section<C: View>(_ title: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.headline)
            content()
        }
        .padding(14)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}
