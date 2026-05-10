import Foundation
import SwiftUI

/// One-sentence natural-language read of the current FocusFrame.
/// Mirrors `nao.process.verdict.Verdict` on the sidecar.
struct Verdict: Codable, Equatable {
    let headline: String
    let detail: String
    let action: String
    let tone: String   // focused | ok | fading | noisy | alert | calm

    var color: Color {
        switch tone {
        case "focused": return .blue
        case "ok":      return .green
        case "fading":  return .orange
        case "alert":   return .red
        case "calm":    return Color(red: 0.55, green: 0.75, blue: 0.95)
        case "noisy":   return .secondary
        default:        return .secondary
        }
    }

    var systemImage: String {
        switch tone {
        case "focused": return "target"
        case "ok":      return "checkmark.circle"
        case "fading":  return "battery.25"
        case "alert":   return "exclamationmark.triangle"
        case "calm":    return "leaf"
        case "noisy":   return "waveform.path.ecg"
        default:        return "circle"
        }
    }
}
