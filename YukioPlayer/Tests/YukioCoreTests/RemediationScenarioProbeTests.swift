import Foundation
import Testing
@testable import YukioCore

/// Export production-parser observations for the shared Python contract checker.
/// This probe is not a claim that the known product defects pass acceptance.
@Suite struct RemediationScenarioProbeTests {
    @Test func exportProductionParserObservations() throws {
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let fixture = root.appendingPathComponent("tests/remediation/fixtures/codex-results.json")
        let document = try #require(JSONSerialization.jsonObject(with: Data(contentsOf: fixture)) as? [String: Any])
        let session = try #require(document["session"] as? String)
        let cases = try #require(document["cases"] as? [[String: Any]])
        #expect(cases.count >= 8)
        let kept: Set<String> = ["activity_end", "activity_failed", "task_abort", "task_failed", "task_end"]
        var observed: [String: Any] = [:]
        for scenario in cases {
            let name = try #require(scenario["id"] as? String)
            let steps = try #require(scenario["steps"] as? [[String: Any]])
            let parser = CodexRolloutParser(session: session)
            observed[name] = try steps.enumerated().map { index, step -> [String: Any] in
                let record = try #require(step["record"] as? [String: Any])
                let events = parser.events(from: record, now: Double(index + 1))
                let facts = try parser.lastToolResults.map { try JSONSerialization.jsonObject(with: JSONEncoder().encode($0)) }
                return ["result": facts.count == 1 ? facts[0] : NSNull(), "events": events.filter { kept.contains($0.kind.rawValue) }.map { event -> [String: Any] in
                    ["kind": event.kind.rawValue, "id": event.eventID as Any? ?? NSNull()]
                }]
            }
        }
        if let path = ProcessInfo.processInfo.environment["YUKIO_SCENARIO_OBSERVATIONS"] {
            let output = try JSONSerialization.data(withJSONObject: observed, options: [.prettyPrinted, .sortedKeys])
            try output.write(to: URL(fileURLWithPath: path), options: .atomic)
        }
    }
}
