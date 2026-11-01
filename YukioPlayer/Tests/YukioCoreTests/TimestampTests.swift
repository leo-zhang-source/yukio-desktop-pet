import Foundation
import Testing
@testable import YukioCore

@Suite struct TimestampTests {
    private static func legacy(_ value: String) -> Double? {
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return (fractional.date(from: value) ?? ISO8601DateFormatter().date(from: value))
            .map { $0.timeIntervalSince1970 * 1000 }
    }

    @Test(arguments: ["2026-11-01T12:34:56Z", "2026-11-01T12:34:56.123Z",
        "2026-11-01T12:34:56.123456Z", "2026-11-01T12:34:56.1Z",
        "2026-11-01T12:34:56+08:00", "2026-11-01T12:34:56.123-07:00",
        "2024-02-29T00:00:00Z", "1970-01-01T00:00:00.000Z",
        "2026-02-30T12:34:56Z", "2026-11-01T25:00:00Z",
        "2026-13-01T12:34:56Z", "2026-00-01T12:34:56Z",
        "2026-11-00T12:34:56Z", "2026-11-32T12:34:56Z",
        "0000-11-01T12:34:56Z", "2026-11-01T12:34:60Z",
        "invalid", "", "2026-11-01"])
    func preservesLegacyFormatsAndPrecision(_ value: String) {
        let expected = Self.legacy(value), actual = PetEvent.parseTimestamp(value)
        if let expected, let actual { #expect(abs(expected - actual) < 0.001) }
        else { #expect(expected == actual) }
        #expect(PetEvent.parseTimestamp(nil) == nil)
    }

    @Test func simultaneousSourcesDoNotShareMutableFormatterState() {
        let inputs = ["2026-11-01T12:34:56Z", "2026-11-01T12:34:56.123Z",
                      "2026-11-01T12:34:56.123456+08:00", "invalid"]
        let expected = inputs.map(Self.legacy)
        DispatchQueue.concurrentPerform(iterations: 200) { index in
            let i = index % inputs.count
            #expect(PetEvent.parseTimestamp(inputs[i]) == expected[i])
        }
    }
}
