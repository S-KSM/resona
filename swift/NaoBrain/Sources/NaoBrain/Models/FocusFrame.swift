import Foundation

struct FocusFrame: Codable, Identifiable, Equatable {
    var id: TimeInterval { ts }

    let ts: TimeInterval
    let alpha: Double
    let beta: Double
    let theta: Double
    let delta: Double
    let gamma: Double
    let focus: Double
    let focusEma: Double
    let artifact: [String]
    let artifactClean: Bool
    let latencyMs: Double
    let alphaPerChannel: [Double]?
    let betaPerChannel: [Double]?
    let frontalFocus: Double?
    let frontalFocusEma: Double?
    let frontalAsymmetry: Double?
    let arousalIndex: Double?
    let deltaRel: Double?
    let thetaRel: Double?
    let alphaRel: Double?
    let betaRel: Double?
    let gammaRel: Double?
    let label: String?
    let quiet: Bool?

    enum CodingKeys: String, CodingKey {
        case ts, alpha, beta, theta, delta, gamma, focus
        case focusEma = "focus_ema"
        case artifact
        case artifactClean = "artifact_clean"
        case latencyMs = "latency_ms"
        case alphaPerChannel = "alpha_per_channel"
        case betaPerChannel = "beta_per_channel"
        case frontalFocus = "frontal_focus"
        case frontalFocusEma = "frontal_focus_ema"
        case frontalAsymmetry = "frontal_asymmetry"
        case arousalIndex = "arousal_index"
        case deltaRel = "delta_rel"
        case thetaRel = "theta_rel"
        case alphaRel = "alpha_rel"
        case betaRel = "beta_rel"
        case gammaRel = "gamma_rel"
        case label, quiet
    }
}

struct BatteryStatus: Codable, Equatable {
    let batteryPct: Double?
    let ageS: Double?
    let stale: Bool

    enum CodingKeys: String, CodingKey {
        case batteryPct = "battery_pct"
        case ageS = "age_s"
        case stale
    }
}

/// BLE link health snapshot — emitted by the sidecar when the headband
/// keeps dropping. UI uses this to swap the generic "Signal stuck" copy
/// for an actionable recovery banner.
struct StreamHealth: Codable, Equatable {
    let unstable: Bool
    let recentDrops: Int
    let lastDropAgeS: Double?

    enum CodingKeys: String, CodingKey {
        case unstable
        case recentDrops = "recent_drops"
        case lastDropAgeS = "last_drop_age_s"
    }
}
