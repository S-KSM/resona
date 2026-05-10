import Foundation
import os

/// Best-effort bridge to macOS Focus modes via the Shortcuts app.
///
/// macOS does not let third-party apps directly toggle Focus through a public
/// API. The standard escape hatch is a user-installed Shortcut that calls the
/// "Set Focus" action; we invoke it by name via `shortcuts run`.
///
/// Setup: user creates two Shortcuts named exactly "Resona Quiet On" and
/// "Resona Quiet Off" that toggle their preferred Focus. We surface a
/// one-button setup hint in the Quiet tab if either shortcut is missing.
///
/// Honest scope: this does NOT intercept third-party app notifications. It
/// flips the OS-level Focus, which the user has already configured to silence
/// what they care about silencing.
@MainActor
enum FocusModeBridge {
    private static let log = Logger(subsystem: "com.nao.brain", category: "FocusModeBridge")

    private static let onShortcut  = "Resona Quiet On"
    private static let offShortcut = "Resona Quiet Off"

    /// Returns true if the named shortcut exists in the user's Shortcuts library.
    static func shortcutExists(_ name: String) -> Bool {
        let out = run("/usr/bin/shortcuts", ["list"]) ?? ""
        return out.split(separator: "\n").contains { $0.trimmingCharacters(in: .whitespaces) == name }
    }

    static func quietOnAvailable() -> Bool { shortcutExists(onShortcut) }
    static func quietOffAvailable() -> Bool { shortcutExists(offShortcut) }

    @discardableResult
    static func enterQuiet() -> Bool {
        guard quietOnAvailable() else {
            log.info("Skipped enterQuiet — '\(onShortcut)' not installed.")
            return false
        }
        return run("/usr/bin/shortcuts", ["run", onShortcut]) != nil
    }

    @discardableResult
    static func leaveQuiet() -> Bool {
        guard quietOffAvailable() else {
            log.info("Skipped leaveQuiet — '\(offShortcut)' not installed.")
            return false
        }
        return run("/usr/bin/shortcuts", ["run", offShortcut]) != nil
    }

    private static func run(_ path: String, _ args: [String]) -> String? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        do {
            try p.run()
            p.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            if p.terminationStatus != 0 {
                log.error("\(path) \(args.joined(separator: " ")) exit=\(p.terminationStatus)")
                return nil
            }
            return String(data: data, encoding: .utf8)
        } catch {
            log.error("Failed to spawn \(path): \(error.localizedDescription)")
            return nil
        }
    }
}
