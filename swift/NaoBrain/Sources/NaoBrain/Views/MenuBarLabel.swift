import SwiftUI

struct MenuBarLabel: View {
    @EnvironmentObject var client: NaoClient

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: "brain.head.profile")
            Text(displayText)
                .font(.system(size: 11, weight: .medium))
                .monospacedDigit()
        }
    }

    private var displayText: String {
        guard let f = client.latestFrame else { return "—" }
        let ema = String(format: "%.2f", f.focusEma)
        if let label = f.label, !label.isEmpty {
            let short = labelShorthand(label)
            return "\(ema) · \(short)"
        }
        return ema
    }

    private func labelShorthand(_ label: String) -> String {
        switch label {
        case "deeply_focused": return "deep"
        case "engaged":        return "engaged"
        case "neutral":        return "neutral"
        case "resting":        return "rest"
        case "uncertain":      return "?"
        default:               return label
        }
    }
}
