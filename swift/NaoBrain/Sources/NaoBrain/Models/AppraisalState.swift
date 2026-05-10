import Foundation

/// Mirrors the Python `Skeptic.state()` + `Skeptic.advise()` blob returned by
/// `GET /appraisal/status`. The Skeptic detects transient frontal-gamma bursts
/// (cognitive reward / "aha" / agreement signals) and tells cooperating agents
/// when to soften affirmation.
struct AppraisalState: Codable, Equatable {
    let recentSpike: Bool
    let sinceSpikeS: Double?
    let baselineN: Int
    let baselineMean: Double?
    let lastZ: Double?
    let caution: Bool
    let cooldownSeconds: Double
    let reason: String

    enum CodingKeys: String, CodingKey {
        case recentSpike = "recent_spike"
        case sinceSpikeS = "since_spike_s"
        case baselineN = "baseline_n"
        case baselineMean = "baseline_mean"
        case lastZ = "last_z"
        case caution
        case cooldownSeconds = "cooldown_seconds"
        case reason
    }
}
