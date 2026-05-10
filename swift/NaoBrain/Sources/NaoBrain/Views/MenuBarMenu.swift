import SwiftUI

struct MenuBarMenu: View {
    @EnvironmentObject var client: NaoClient
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        if let f = client.latestFrame {
            Text(String(format: "Focus EMA: %.3f", f.focusEma))
            Text("Label: \(f.label ?? "—")")
            Text(String(format: "α %.2f  β %.2f  θ %.2f", f.alpha, f.beta, f.theta))
            if !f.artifact.isEmpty {
                Text("Artifacts: \(f.artifact.joined(separator: ", "))")
            }
        } else {
            Text("Pipeline warming up…")
        }

        Divider()

        if let g = client.gatekeeper {
            Text(g.quiet ? "🔕 QUIET — \(g.queuedCount) queued" : "🔔 Open")
            if g.quiet {
                Button("Force OPEN") {
                    Task { await client.overrideGatekeeper("OPEN") }
                }
            } else {
                Button("Force QUIET") {
                    Task { await client.overrideGatekeeper("QUIET") }
                }
            }
            if g.queuedCount > 0 {
                Button("Release queued (\(g.queuedCount))") {
                    Task { await client.overrideGatekeeper("release") }
                }
            }
            Divider()
        }

        if let a = client.appraisal, a.caution {
            Text(String(format: "⚠︎ Skeptic caution — %.0fs cooldown", a.cooldownSeconds))
            Divider()
        }

        Button("Open Resona") { openWindow(id: "main") }
            .keyboardShortcut("n", modifiers: [.command, .shift])

        Button("Restart pipeline") {
            Task { await client.restartPipeline() }
        }

        Divider()

        Button("Quit") { NSApplication.shared.terminate(nil) }
            .keyboardShortcut("q")
    }
}
