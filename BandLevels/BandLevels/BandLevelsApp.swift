import SwiftUI

@main
struct BandLevelsApp: App {
    @State private var settings: AppSettings
    @State private var model: DashboardModel

    init() {
        FontRegistry.shared.load()
        let settings = AppSettings()
        _settings = State(initialValue: settings)
        _model = State(initialValue: DashboardModel(settings: settings))
    }

    var body: some Scene {
        WindowGroup {
            DashboardView(model: model, settings: settings)
                .task { await model.run() }
        }
    }
}
