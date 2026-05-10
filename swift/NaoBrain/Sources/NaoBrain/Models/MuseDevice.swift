import Foundation

struct MuseDevice: Codable, Hashable, Identifiable {
    let address: String
    let name: String

    var id: String { address }
}

struct ChannelQuality: Codable, Hashable, Identifiable {
    let channel: String
    let stdUv: Double
    let verdict: String  // ok | weak | FLAT | noisy

    var id: String { channel }

    enum CodingKeys: String, CodingKey {
        case channel
        case stdUv = "std_uv"
        case verdict
    }
}

struct SignalQuality: Codable, Equatable {
    let status: String
    let current: CurrentState?
    let signalQuality: [ChannelQuality]?

    enum CodingKeys: String, CodingKey {
        case status, current
        case signalQuality = "signal_quality"
    }
}

struct CurrentState: Codable, Equatable {
    let focusEma: Double?
    let alpha: Double?
    let beta: Double?
    let theta: Double?
    let label: String?
    let artifactFlags: [String]?
    let artifactClean: Bool?

    enum CodingKeys: String, CodingKey {
        case focusEma = "focus_ema"
        case alpha, beta, theta, label
        case artifactFlags = "artifact_flags"
        case artifactClean = "artifact_clean"
    }
}
