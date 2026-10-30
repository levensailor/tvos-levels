import SwiftUI

/// Public settings: bridge address, metric emphasis, display refresh, and bridge measurement periods.
struct SettingsView: View {
    let model: DashboardModel
    @Bindable var settings: AppSettings

    @State private var host = ""
    @State private var port = ""
    @State private var streamPath = ""
    @State private var periodsPath = ""
    @State private var connectionMessage: String?
    @State private var draftPeriods = SettingsView.placeholderPeriods
    @State private var periodsLoaded = false

    private static let placeholderPeriods = BridgePeriods(
        dbfsPeakWindowMs: PeriodField.dbfsPeakWindow.range.lowerBound,
        vuIntegrationMs: PeriodField.vuIntegration.range.lowerBound,
        lufsWindowMs: PeriodField.lufsWindow.range.lowerBound,
        logicPollMs: PeriodField.logicPoll.range.lowerBound,
        publishIntervalMs: PeriodField.publishInterval.range.lowerBound,
        staleAfterMs: PeriodField.staleAfter.range.lowerBound
    )

    var body: some View {
        NavigationStack {
            Form {
                connectionSection
                displaySection
                periodsSection
                sourcesSection
                if let rejection = model.lastRejection {
                    Section("Last rejected payload") {
                        Text(rejection)
                        LabeledContent("Rejected so far", value: "\(model.rejectedPayloads)")
                    }
                }
            }
            .navigationTitle("Settings")
        }
        .onAppear(perform: load)
        .onChange(of: model.periods) { _, newValue in
            if let newValue, !periodsLoaded {
                draftPeriods = newValue
                periodsLoaded = true
            }
        }
    }

    private var connectionSection: some View {
        Section {
            TextField("Bridge host (IP or name.local)", text: $host)
            TextField("Port", text: $port)
            TextField("Stream path", text: $streamPath)
            TextField("Periods path", text: $periodsPath)
            Button("Save and reconnect", action: saveConnection)
            if let connectionMessage {
                Text(connectionMessage)
            }
            LabeledContent("Status", value: model.connection.label)
        } header: {
            Text("Bridge connection")
        } footer: {
            Text("No login is required. The dashboard reads the local bridge on your network.")
        }
    }

    private var displaySection: some View {
        Section("Display") {
            Picker("Emphasized metric", selection: $settings.emphasis) {
                ForEach(MetricKind.allCases) { metric in
                    Text(metric.title).tag(metric)
                }
            }
            Picker("Display refresh period", selection: $settings.displayRefreshMilliseconds) {
                ForEach(AppSettings.displayRefreshOptions, id: \.self) { value in
                    Text("\(value) ms").tag(value)
                }
            }
        }
    }

    private var periodsSection: some View {
        Section {
            if periodsLoaded {
                ForEach(PeriodField.allCases) { field in
                    Picker(field.title, selection: $draftPeriods[field]) {
                        ForEach(field.options(including: draftPeriods[field]), id: \.self) { value in
                            Text("\(value) ms").tag(value)
                        }
                    }
                }
                Button("Apply to bridge") {
                    let requested = draftPeriods
                    Task { await model.applyPeriods(requested) }
                }
                if let status = model.periodsStatus {
                    Text(status)
                }
            } else {
                Text("Connect to the bridge to load its measurement periods.")
            }
        } header: {
            Text("Measurement periods")
        } footer: {
            Text("Windows for dBFS peak, VU integration, and LUFS, plus how often the bridge polls Logic and publishes.")
        }
    }

    private var sourcesSection: some View {
        Section("Level sources") {
            if model.sources.isEmpty {
                Text("Waiting for the bridge")
            }
            ForEach(model.sources) { source in
                LabeledContent(
                    source.name,
                    value: source.enabled ? (source.connected ? "Connected — \(source.detail)" : source.detail) : "Disabled"
                )
            }
        }
    }

    private func load() {
        host = settings.bridgeHost
        port = String(settings.bridgePort)
        streamPath = settings.streamPath
        periodsPath = settings.periodsPath
        if let periods = model.periods {
            draftPeriods = periods
            periodsLoaded = true
        }
    }

    private func saveConnection() {
        let trimmedHost = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedHost.isEmpty else {
            connectionMessage = "Host is required."
            return
        }
        guard let portNumber = Int(port.trimmingCharacters(in: .whitespaces)),
              AppSettings.portRange.contains(portNumber) else {
            connectionMessage = "Port must be a number from 1 to 65535."
            return
        }
        guard streamPath.hasPrefix("/"), periodsPath.hasPrefix("/") else {
            connectionMessage = "Paths must start with /."
            return
        }
        settings.bridgeHost = trimmedHost
        settings.bridgePort = portNumber
        settings.streamPath = streamPath
        settings.periodsPath = periodsPath
        if let problem = settings.connectionProblem {
            connectionMessage = problem
            return
        }
        connectionMessage = "Saved. Reconnecting…"
        periodsLoaded = false
        model.reconnect()
    }
}
