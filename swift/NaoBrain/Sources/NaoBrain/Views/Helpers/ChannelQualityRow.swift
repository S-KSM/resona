import SwiftUI

struct ChannelQualityRow: View {
    let quality: ChannelQuality

    var body: some View {
        VStack(spacing: 4) {
            Text(quality.channel)
                .font(.caption.bold())
            Text(String(format: "%.0f µV", quality.stdUv))
                .font(.caption2)
                .foregroundStyle(.secondary)
                .monospacedDigit()
            Text(quality.verdict)
                .font(.caption2)
                .foregroundStyle(verdictColor)
        }
        .padding(8)
        .frame(minWidth: 70)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8))
    }

    private var verdictColor: Color {
        switch quality.verdict {
        case "ok":     return .green
        case "weak":   return .yellow
        case "FLAT":   return .red
        case "noisy":  return .orange
        default:       return .secondary
        }
    }
}
