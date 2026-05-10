import SwiftUI

@main
struct NaoBrainApp: App {
    @StateObject private var client = NaoClient()

    var body: some Scene {
        WindowGroup("NAO Brain") {
            RootView()
                .environmentObject(client)
                .frame(minWidth: 900, minHeight: 600)
                .onAppear { client.start() }
                .onDisappear { client.stop() }
        }
        .windowResizability(.contentSize)

        MenuBarExtra {
            MenuBarMenu()
                .environmentObject(client)
        } label: {
            MenuBarLabel()
                .environmentObject(client)
        }
        .menuBarExtraStyle(.menu)
    }
}
