import Foundation

/// Snapshot returned by GET /gatekeeper/status — the FSM state the UI renders.
struct GatekeeperStatus: Codable, Equatable {
    let quiet: Bool
    let sinceTs: TimeInterval?
    let queuedCount: Int
    let lastLabel: String
    let lastDecisionReason: String

    enum CodingKeys: String, CodingKey {
        case quiet
        case sinceTs = "since_ts"
        case queuedCount = "queued_count"
        case lastLabel = "last_label"
        case lastDecisionReason = "last_decision_reason"
    }
}

/// One ping that was deferred while the FSM was QUIET.
struct QueuedPing: Codable, Identifiable, Equatable {
    let id: String
    let source: String
    let summary: String
    let urgency: String
}

/// Response payload from POST /gatekeeper/override with target=release.
struct GatekeeperReleased: Codable {
    let status: String
    let releasedCount: Int
    let items: [QueuedPing]

    enum CodingKeys: String, CodingKey {
        case status
        case releasedCount = "released_count"
        case items
    }
}
