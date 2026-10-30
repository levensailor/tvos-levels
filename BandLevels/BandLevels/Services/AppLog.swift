import Foundation
import os

/// Unified-logging categories. Every entry carries file, line, and function.
enum AppLog {
    static let subsystem = Bundle.main.bundleIdentifier ?? "BandLevels"
    static let bridge = Logger(subsystem: subsystem, category: "bridge")
    static let ui = Logger(subsystem: subsystem, category: "ui")

    static func info(
        _ logger: Logger, _ message: String,
        file: String = #fileID, line: Int = #line, function: String = #function
    ) {
        logger.info("\(file, privacy: .public):\(line, privacy: .public) \(function, privacy: .public) - \(message, privacy: .public)")
    }

    static func warning(
        _ logger: Logger, _ message: String,
        file: String = #fileID, line: Int = #line, function: String = #function
    ) {
        logger.warning("\(file, privacy: .public):\(line, privacy: .public) \(function, privacy: .public) - \(message, privacy: .public)")
    }

    static func error(
        _ logger: Logger, _ message: String,
        file: String = #fileID, line: Int = #line, function: String = #function
    ) {
        logger.error("\(file, privacy: .public):\(line, privacy: .public) \(function, privacy: .public) - \(message, privacy: .public)")
    }
}
