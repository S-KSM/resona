import Foundation

struct SessionSummary: Codable, Equatable {
    let frameCount: Int
    let cleanFrameCount: Int
    let durationS: Double
    let focusMean: Double?
    let focusStd: Double?
    let alphaMean: Double?
    let betaMean: Double?
    let thetaMean: Double?
    let artifactRate: Double
    let asymmetryMean: Double?
    let arousalMean: Double?

    enum CodingKeys: String, CodingKey {
        case frameCount = "frame_count"
        case cleanFrameCount = "clean_frame_count"
        case durationS = "duration_s"
        case focusMean = "focus_mean"
        case focusStd = "focus_std"
        case alphaMean = "alpha_mean"
        case betaMean = "beta_mean"
        case thetaMean = "theta_mean"
        case artifactRate = "artifact_rate"
        case asymmetryMean = "asymmetry_mean"
        case arousalMean = "arousal_mean"
    }
}

struct Session: Codable, Identifiable, Equatable {
    let id: String
    let label: String
    let startedAt: Double
    let endedAt: Double?
    let notes: String
    let summary: SessionSummary

    var isActive: Bool { endedAt == nil }

    enum CodingKeys: String, CodingKey {
        case id, label, notes, summary
        case startedAt = "started_at"
        case endedAt = "ended_at"
    }
}

enum SessionLabelSuggestion: String, CaseIterable, Identifiable {
    case meditate, sleep
    case deepWork = "deep_work"
    case coding, reading, meeting, rest, other

    var id: String { rawValue }

    var display: String {
        switch self {
        case .deepWork: return "deep work"
        default: return rawValue
        }
    }
}
