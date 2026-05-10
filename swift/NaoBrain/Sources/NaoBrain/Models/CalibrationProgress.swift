import Foundation

struct CalibrationResult: Codable, Equatable {
    let meanF: Double
    let stdF: Double
    let nSamples: Int
    let savedAt: Double?    // epoch seconds, missing on pre-drift baselines
    let ageDays: Double?    // server-computed; nil when savedAt unknown
    let isStale: Bool?

    enum CodingKeys: String, CodingKey {
        case meanF = "mean_f"
        case stdF = "std_f"
        case nSamples = "n_samples"
        case savedAt = "saved_at"
        case ageDays = "age_days"
        case isStale = "is_stale"
    }
}

struct CalibrationProgress: Codable, Equatable {
    let phase: String  // idle | eyes_open | eyes_closed | saving | done | error
    let secondsRemaining: Double?
    let secondsTotal: Double?
    let nEyesOpen: Int?
    let nEyesClosed: Int?
    let result: CalibrationResult?
    let error: String?
    let artifactCounts: [String: Int]?

    enum CodingKeys: String, CodingKey {
        case phase
        case secondsRemaining = "seconds_remaining"
        case secondsTotal = "seconds_total"
        case nEyesOpen = "n_eyes_open"
        case nEyesClosed = "n_eyes_closed"
        case result, error
        case artifactCounts = "artifact_counts"
    }

    var isRunning: Bool {
        ["eyes_open", "eyes_closed", "saving"].contains(phase)
    }
}
