import AVFoundation

/// Native macOS TTS wrapper. AVSpeechSynthesizer ships with the OS and
/// includes Premium / Enhanced / Neural voices that don't need manual install.
final class SpeechService {

    static let shared = SpeechService()

    private let synth = AVSpeechSynthesizer()

    /// All English voices, sorted with Premium / Enhanced first.
    static func availableVoices() -> [AVSpeechSynthesisVoice] {
        AVSpeechSynthesisVoice.speechVoices()
            .filter { $0.language.lowercased().hasPrefix("en") }
            .sorted { lhs, rhs in
                let lp = lhs.quality.priority
                let rp = rhs.quality.priority
                if lp != rp { return lp > rp }
                return lhs.name < rhs.name
            }
    }

    /// Default — first Premium English voice if installed, else first available.
    static func defaultVoice() -> AVSpeechSynthesisVoice? {
        availableVoices().first
    }

    func speak(_ text: String, voiceIdentifier: String? = nil, rate: Float = 0.5) {
        let utt = AVSpeechUtterance(string: text)
        if let id = voiceIdentifier, let voice = AVSpeechSynthesisVoice(identifier: id) {
            utt.voice = voice
        } else {
            utt.voice = AVSpeechSynthesisVoice(language: "en-US")
        }
        utt.rate = rate
        synth.speak(utt)
    }

    func stop() {
        synth.stopSpeaking(at: .immediate)
    }

    var isSpeaking: Bool {
        synth.isSpeaking
    }
}

private extension AVSpeechSynthesisVoiceQuality {
    /// Sort priority: Premium > Enhanced > Default.
    var priority: Int {
        switch self {
        case .premium: return 2
        case .enhanced: return 1
        default: return 0
        }
    }
}
