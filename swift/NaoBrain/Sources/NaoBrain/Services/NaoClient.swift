import Foundation
import os

/// Client that talks to the Python sidecar (FastAPI on localhost:8765).
///
/// Holds the latest FocusFrame + a rolling history. SSE keeps the UI live
/// without polling. REST methods mutate config / drive calibration.
@MainActor
final class NaoClient: ObservableObject {

    // MARK: Published state

    @Published var isConnected: Bool = false
    @Published var lastError: String?
    @Published var latestFrame: FocusFrame?
    @Published var history: [FocusFrame] = []
    @Published var config: NaoConfig?
    @Published var calibration: CalibrationResult?
    @Published var calibrationProgress: CalibrationProgress?
    @Published var signalQuality: SignalQuality?
    @Published var llmAvailable: Bool = false
    @Published var llmModels: [String] = []
    @Published var gatekeeper: GatekeeperStatus?
    @Published var lastReleased: [QueuedPing] = []
    @Published var queuedPings: [QueuedPing] = []
    @Published var appraisal: AppraisalState?
    @Published var activeSession: Session?
    @Published var sessions: [Session] = []

    // MARK: Internals

    private let baseURL = URL(string: "http://127.0.0.1:8765")!
    private var sseTask: Task<Void, Never>?
    private var pollTask: Task<Void, Never>?
    private var stateTask: Task<Void, Never>?
    private let log = Logger(subsystem: "com.nao.brain", category: "NaoClient")

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        return d
    }()

    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        return e
    }()

    /// Max frames retained for charts. ~30s at 4 Hz.
    private let historyMax = 240

    // MARK: Lifecycle

    func start() {
        Task { await self.refreshAll() }
        sseTask?.cancel()
        sseTask = Task { await self.streamFrames() }
        pollTask?.cancel()
        pollTask = Task { await self.pollLoop() }
        stateTask?.cancel()
        stateTask = Task { await self.statePollLoop() }
    }

    func stop() {
        sseTask?.cancel()
        pollTask?.cancel()
        stateTask?.cancel()
    }

    // 4 Hz REST fallback so the Live tab works even when SSE is wedged
    // (URLSession.AsyncBytes buffering can swallow chunked frames on macOS).
    private func statePollLoop() async {
        while !Task.isCancelled {
            await loadState()
            try? await Task.sleep(nanoseconds: 250_000_000)
        }
    }

    private func loadState() async {
        let req = URLRequest(url: baseURL.appending(path: "/state"))
        guard let (data, _) = try? await URLSession.shared.data(for: req) else {
            print("[loadState] HTTP failed")
            return
        }
        do {
            let frame = try decoder.decode(FocusFrame.self, from: data)
            if let last = self.latestFrame, last.ts == frame.ts { return }
            // Source changed (synthetic monotonic vs Muse epoch) → drop stale history
            // so the chart x-axis doesn't span the 1.7e9-second gap.
            if let last = self.history.last, abs(frame.ts - last.ts) > 60 {
                self.history.removeAll()
            }
            self.latestFrame = frame
        } catch {
            return
        }
        guard let frame = self.latestFrame else { return }
        self.history.append(frame)
        if self.history.count > self.historyMax {
            self.history.removeFirst(self.history.count - self.historyMax)
        }
        self.isConnected = true
    }

    // MARK: Refresh

    func refreshAll() async {
        await loadConfig()
        await loadCalibration()
        await loadSignalQuality()
        await loadLLMHealth()
        await loadGatekeeperStatus()
        await loadAppraisalStatus()
        await loadActiveSession()
        await loadSessions()
    }

    func loadAppraisalStatus() async {
        if let s: AppraisalState = try? await get("/appraisal/status") {
            self.appraisal = s
        }
    }

    // MARK: Endpoints

    func loadConfig() async {
        do {
            let cfg: NaoConfig = try await get("/config")
            self.config = cfg
            self.isConnected = true
            self.lastError = nil
        } catch {
            self.lastError = describe(error)
            self.isConnected = false
        }
    }

    func saveConfig(_ patch: ConfigPatch) async {
        do {
            let updated: NaoConfig = try await post("/config", body: patch)
            self.config = updated
        } catch {
            self.lastError = describe(error)
        }
    }

    func scanMuse(timeout: Double = 8.0) async -> [MuseDevice] {
        do {
            return try await get("/sources/scan?timeout=\(timeout)")
        } catch {
            self.lastError = describe(error)
            return []
        }
    }

    func restartPipeline() async {
        _ = try? await postRaw("/pipeline/restart", body: EmptyBody())
    }

    func loadCalibration() async {
        let result: CalibrationResult? = (try? await getOptional("/calibration"))
        self.calibration = result
    }

    func loadSignalQuality() async {
        let q: SignalQuality? = (try? await getOptional("/signal/quality"))
        self.signalQuality = q
    }

    struct CalibrateStartReq: Codable {
        let secondsPerPhase: Double
        enum CodingKeys: String, CodingKey { case secondsPerPhase = "seconds_per_phase" }
    }

    func startCalibration(secondsPerPhase: Double) async {
        do {
            let p: CalibrationProgress = try await post(
                "/calibrate/start",
                body: CalibrateStartReq(secondsPerPhase: secondsPerPhase)
            )
            self.calibrationProgress = p
        } catch {
            self.lastError = describe(error)
        }
    }

    func cancelCalibration() async {
        _ = try? await postRaw("/calibrate/cancel", body: EmptyBody())
    }

    func resetCalibration() async {
        _ = try? await postRaw("/calibrate/reset", body: EmptyBody())
        self.calibrationProgress = nil
    }

    // MARK: Gatekeeper

    struct GatekeeperQueueReq: Codable {
        let source: String
        let summary: String
        let urgency: String
    }

    struct GatekeeperOverrideReq: Codable {
        let target: String  // OPEN | QUIET | release
    }

    private var lastBridgeQuiet: Bool = false

    func loadGatekeeperStatus() async {
        if let s: GatekeeperStatus = try? await get("/gatekeeper/status") {
            self.gatekeeper = s
            // Drive the macOS Focus bridge on edge transitions only — avoid
            // re-firing the Shortcut on every poll.
            if s.quiet != lastBridgeQuiet {
                lastBridgeQuiet = s.quiet
                if s.quiet {
                    _ = FocusModeBridge.enterQuiet()
                } else {
                    _ = FocusModeBridge.leaveQuiet()
                }
            }
            // Refresh queued list whenever count changed; cheap read-only peek.
            if (s.queuedCount != self.queuedPings.count) {
                await loadQueuedPings()
            }
        }
    }

    func loadQueuedPings() async {
        if let pings: [QueuedPing] = try? await get("/gatekeeper/queued") {
            self.queuedPings = pings
        }
    }

    func enqueueGatekeeperPing(source: String, summary: String, urgency: String) async {
        struct R: Codable { let queuedId: String; let queuedCount: Int
            enum CodingKeys: String, CodingKey {
                case queuedId = "queued_id"; case queuedCount = "queued_count"
            }
        }
        do {
            _ = try await post(
                "/gatekeeper/queue",
                body: GatekeeperQueueReq(source: source, summary: summary, urgency: urgency)
            ) as R
            await loadGatekeeperStatus()
        } catch {
            self.lastError = describe(error)
        }
    }

    func overrideGatekeeper(_ target: String) async {
        if target.uppercased() == "RELEASE" {
            do {
                let r: GatekeeperReleased = try await post(
                    "/gatekeeper/override",
                    body: GatekeeperOverrideReq(target: "release")
                )
                self.lastReleased = r.items
                await loadGatekeeperStatus()
            } catch {
                self.lastError = describe(error)
            }
            return
        }
        do {
            let s: GatekeeperStatus = try await post(
                "/gatekeeper/override",
                body: GatekeeperOverrideReq(target: target)
            )
            self.gatekeeper = s
        } catch {
            self.lastError = describe(error)
        }
    }

    // MARK: Sessions

    struct SessionStartReq: Codable {
        let label: String
        let notes: String
    }

    func loadActiveSession() async {
        let s: Session? = (try? await getOptional("/session/active"))
        self.activeSession = s
    }

    func loadSessions() async {
        if let xs: [Session] = try? await get("/sessions") {
            self.sessions = xs.sorted { $0.startedAt > $1.startedAt }
        }
    }

    @discardableResult
    func startSession(label: String, notes: String = "") async -> Session? {
        do {
            let s: Session = try await post(
                "/session/start",
                body: SessionStartReq(label: label, notes: notes)
            )
            self.activeSession = s
            return s
        } catch {
            self.lastError = describe(error)
            return nil
        }
    }

    @discardableResult
    func stopSession() async -> Session? {
        do {
            let s: Session = try await post("/session/stop", body: EmptyBody())
            self.activeSession = nil
            await loadSessions()
            return s
        } catch {
            self.lastError = describe(error)
            return nil
        }
    }

    func deleteSession(_ id: String) async {
        var req = URLRequest(url: url("/session/\(id)"))
        req.httpMethod = "DELETE"
        _ = try? await URLSession.shared.data(for: req)
        await loadSessions()
    }

    struct SessionFramePoint: Codable, Identifiable {
        let ts: Double
        let focusEma: Double
        let focus: Double
        let alpha: Double
        let beta: Double
        let frontalAsymmetry: Double?
        let arousalIndex: Double?
        let artifactClean: Bool
        var id: Double { ts }
        enum CodingKeys: String, CodingKey {
            case ts, focus, alpha, beta
            case focusEma = "focus_ema"
            case frontalAsymmetry = "frontal_asymmetry"
            case arousalIndex = "arousal_index"
            case artifactClean = "artifact_clean"
        }
    }

    func loadSessionFrames(_ id: String, step: Int = 1) async -> [SessionFramePoint] {
        if let xs: [SessionFramePoint] = try? await get("/session/\(id)/frames?step=\(step)") {
            return xs
        }
        return []
    }

    /// Loose-typed session digest. Rendered as JSON-pretty in the UI; structured
    /// fields are pulled out via the `SessionInsights` accessor below.
    struct SessionInsights: Codable {
        let id: String
        let label: String
        let summary: SessionSummary
        let trendSlopePerMin: Double?
        let biggestDrop: BiggestDrop?
        let quartiles: Quartiles
        let vsCalibration: VsCalibration?
        let vsLabelBaseline: VsLabelBaseline?

        struct Quartiles: Codable {
            let q1: Double?
            let q2: Double?
            let q3: Double?
            let q4: Double?
        }

        struct BiggestDrop: Codable {
            let tMinute: Double
            let focusMean: Double
            let deltaVsSessionMean: Double
            enum CodingKeys: String, CodingKey {
                case tMinute = "t_minute"
                case focusMean = "focus_mean"
                case deltaVsSessionMean = "delta_vs_session_mean"
            }
        }

        struct VsCalibration: Codable {
            let zScore: Double
            let userMeanF: Double
            let userStdF: Double
            enum CodingKeys: String, CodingKey {
                case zScore = "z_score"
                case userMeanF = "user_mean_f"
                case userStdF = "user_std_f"
            }
        }

        struct VsLabelBaseline: Codable {
            let label: String
            let nPrior: Int
            let labelFocusMean: Double
            let delta: Double?
            enum CodingKeys: String, CodingKey {
                case label
                case nPrior = "n_prior"
                case labelFocusMean = "label_focus_mean"
                case delta
            }
        }

        enum CodingKeys: String, CodingKey {
            case id, label, summary, quartiles
            case trendSlopePerMin = "trend_slope_per_min"
            case biggestDrop = "biggest_drop"
            case vsCalibration = "vs_calibration"
            case vsLabelBaseline = "vs_label_baseline"
        }
    }

    func loadSessionInsights(_ id: String) async -> SessionInsights? {
        try? await get("/session/\(id)/insights")
    }

    func sessionChat(
        _ sessionId: String, messages: [ChatMsg], model: String? = nil, temperature: Double = 0.4
    ) async throws -> String {
        struct R: Codable { let reply: String; let model: String }
        let r: R = try await post(
            "/session/\(sessionId)/chat",
            body: ChatReq(messages: messages, temperature: temperature, model: model)
        )
        return r.reply
    }

    // MARK: LLM

    func loadLLMHealth() async {
        struct H: Codable { let available: Bool }
        if let h: H = try? await get("/llm/health") {
            self.llmAvailable = h.available
        } else {
            self.llmAvailable = false
        }
        if self.llmAvailable {
            self.llmModels = (try? await get("/llm/models")) ?? []
        }
    }

    struct ProseReq: Codable {
        let seed: Int?
        let model: String?
    }

    func calibrationProse(seed: Int? = nil, model: String? = nil) async -> String? {
        struct R: Codable { let text: String }
        do {
            let r: R = try await post("/llm/prose", body: ProseReq(seed: seed, model: model))
            return r.text
        } catch {
            return nil
        }
    }

    struct ChatMsg: Codable, Identifiable {
        var id = UUID()
        let role: String  // user | assistant | system
        let content: String

        enum CodingKeys: String, CodingKey { case role, content }
    }

    struct ChatReq: Codable {
        let messages: [ChatMsg]
        let temperature: Double
        let model: String?
    }

    func chat(messages: [ChatMsg], model: String? = nil, temperature: Double = 0.4) async throws -> String {
        struct R: Codable { let reply: String; let model: String }
        let r: R = try await post(
            "/llm/chat",
            body: ChatReq(messages: messages, temperature: temperature, model: model)
        )
        return r.reply
    }

    // MARK: Streams

    private func streamFrames() async {
        while !Task.isCancelled {
            do {
                try await consumeSSE()
            } catch {
                self.isConnected = false
                self.lastError = "SSE: \(describe(error))"
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
        }
    }

    private func consumeSSE() async throws {
        var req = URLRequest(url: baseURL.appending(path: "/events"))
        req.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        let (bytes, response) = try await URLSession.shared.bytes(for: req)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        self.isConnected = true

        var dataBuf = ""
        for try await line in bytes.lines {
            if line.hasPrefix("data: ") {
                dataBuf = String(line.dropFirst(6))
            } else if line.isEmpty, !dataBuf.isEmpty {
                if let payload = dataBuf.data(using: .utf8),
                   let frame = try? decoder.decode(FocusFrame.self, from: payload) {
                    self.latestFrame = frame
                    self.history.append(frame)
                    if self.history.count > self.historyMax {
                        self.history.removeFirst(self.history.count - self.historyMax)
                    }
                }
                dataBuf = ""
            }
        }
    }

    private func pollLoop() async {
        var tick = 0
        while !Task.isCancelled {
            try? await Task.sleep(nanoseconds: 1_000_000_000)
            await loadSignalQuality()
            // Refresh Gatekeeper every 2 s — edge transitions drive the
            // FocusModeBridge so we don't need it faster than that.
            tick += 1
            if tick % 2 == 0 {
                await loadGatekeeperStatus()
                await loadAppraisalStatus()
                if self.activeSession != nil {
                    await loadActiveSession()
                }
            }
            if let p = self.calibrationProgress, p.isRunning {
                await pollCalibrationProgress()
            }
        }
    }

    func pollCalibrationProgress() async {
        if let p: CalibrationProgress = try? await get("/calibrate/progress") {
            self.calibrationProgress = p
            if p.phase == "done" {
                await loadCalibration()
            }
        }
    }

    // MARK: HTTP helpers

    private struct EmptyBody: Codable {}

    /// Build a URL from a relative path string. Uses `URL(string:relativeTo:)`
    /// so that query strings in the path (e.g. "/sources/scan?timeout=8")
    /// are parsed as queries — `URL.appending(path:)` would percent-encode
    /// the `?` and silently break the request.
    private func url(_ path: String) -> URL {
        URL(string: path, relativeTo: baseURL) ?? baseURL.appending(path: path)
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let req = URLRequest(url: url(path))
        let (data, _) = try await URLSession.shared.data(for: req)
        return try decoder.decode(T.self, from: data)
    }

    private func getOptional<T: Decodable>(_ path: String) async throws -> T? {
        let req = URLRequest(url: url(path))
        let (data, _) = try await URLSession.shared.data(for: req)
        if data.isEmpty || data == "null".data(using: .utf8) { return nil }
        return try decoder.decode(T.self, from: data)
    }

    private func post<B: Encodable, T: Decodable>(_ path: String, body: B) async throws -> T {
        var req = URLRequest(url: url(path))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(body)
        let (data, response) = try await URLSession.shared.data(for: req)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            let msg = String(data: data, encoding: .utf8) ?? "HTTP \(http.statusCode)"
            throw NSError(domain: "NaoClient", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: msg])
        }
        return try decoder.decode(T.self, from: data)
    }

    @discardableResult
    private func postRaw<B: Encodable>(_ path: String, body: B) async throws -> Data {
        var req = URLRequest(url: url(path))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(body)
        let (data, _) = try await URLSession.shared.data(for: req)
        return data
    }

    private func describe(_ error: Error) -> String {
        if let urlErr = error as? URLError {
            return "Sidecar not reachable (\(urlErr.localizedDescription)). Start: `uv run nao-sidecar`."
        }
        return error.localizedDescription
    }
}
