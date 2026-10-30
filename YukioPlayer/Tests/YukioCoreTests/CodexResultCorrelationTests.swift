import Foundation
import Testing
@testable import YukioCore

@Suite struct CodexResultCorrelationTests {
    private func parse(_ p: CodexRolloutParser, _ row: [String: Any]) -> [PetEvent] {
        p.events(from: row, now: 1234)
    }

    @Test func sharedCasesPreserveTheirExpectedEventsAndFacts() throws {
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let doc = try #require(JSONSerialization.jsonObject(with: Data(contentsOf:
            root.appendingPathComponent("tests/remediation/fixtures/codex-results.json"))) as? [String: Any])
        let cases = try #require(doc["cases"] as? [[String: Any]])
        let kept: Set<String> = ["activity_end", "activity_failed", "task_abort", "task_failed", "task_end"]
        for scenario in cases {
            let p = CodexRolloutParser(session: try #require(doc["session"] as? String))
            for step in try #require(scenario["steps"] as? [[String: Any]]) {
                let events = parse(p, try #require(step["record"] as? [String: Any]))
                let actual = events.filter { kept.contains($0.kind.rawValue) }.map {
                    ["kind": $0.kind.rawValue, "id": $0.eventID as Any? ?? NSNull()]
                }
                #expect((actual as NSArray).isEqual(step["expect_events"] as? NSArray), "\(scenario["id"] ?? "case")")
                if let expected = step["expect_result"] as? [String: Any] {
                    let fact = try #require(p.lastToolResults.first)
                    let fields = try #require(JSONSerialization.jsonObject(with: JSONEncoder().encode(fact)) as? [String: Any])
                    for (key, value) in expected {
                        #expect((fields[key] as? NSObject) == (value as? NSObject), "\(scenario["id"] ?? "case"): \(key)")
                    }
                }
            }
        }
    }

    @Test func unlinkedFailureNeverBecomesTheNextCallsFailure() {
        let p = CodexRolloutParser(session: "s")
        _ = parse(p, ["type": "item_completed", "item": ["type": "CommandExecution", "status": "failed"]])
        #expect(p.lastToolResults.first?.association == "unlinked")
        #expect(p.lastToolResults.first?.outcome == .failed)
        let end = parse(p, ["type": "function_call_output", "call_id": "a", "output": "plain text"])
        #expect(end.first?.kind == .activityEnd)
        #expect(p.lastToolResults.first?.callOutcome == .unknown)
    }

    @Test func staleBoundaryCannotCloseANewerTurnAndReusedIdentityIsAmbiguous() {
        let p = CodexRolloutParser(session: "s")
        _ = parse(p, ["type": "task_started", "turn_id": "old"])
        _ = parse(p, ["type": "function_call", "name": "shell", "call_id": "a"])
        _ = parse(p, ["type": "task_started", "turn_id": "new"])
        _ = parse(p, ["type": "function_call", "name": "shell", "call_id": "a"])
        #expect(parse(p, ["type": "turn_aborted", "turn_id": "old"]).isEmpty)
        #expect(parse(p, ["type": "function_call_output", "call_id": "a", "output": ["success": false]]).isEmpty)
        #expect(p.lastToolResults.first?.turnAssociation == "ambiguous_reused_call")
        #expect(parse(p, ["type": "function_call_output", "call_id": "a", "turn_id": "new", "output": ["success": true]]).first?.kind == .activityEnd)
    }

    @Test func aSessionChangeAndAMissingTurnBoundaryDoNotLeakOldFailures() {
        let p = CodexRolloutParser(session: "old")
        _ = parse(p, ["type": "function_call", "name": "shell", "call_id": "a"])
        _ = parse(p, ["type": "item_completed", "item": ["type": "CommandExecution", "call_id": "a", "status": "failed"]])
        _ = parse(p, ["type": "session_meta", "id": "new"])
        #expect(parse(p, ["type": "function_call_output", "call_id": "a", "output": "unknown"]).first?.kind == .activityEnd)
        #expect(p.lastToolResults.first?.callOutcome == .unknown)
        _ = parse(p, ["type": "task_started"])
        #expect(parse(p, ["type": "function_call_output", "call_id": "a", "output": ["success": false]]).isEmpty)
    }

    @Test func conflictingEvidenceStaysUnknownAndMalformedLinesClearOnlyLatestObservation() {
        let p = CodexRolloutParser(session: "s")
        for status in ["failed", "failed", "succeeded"] {
            _ = parse(p, ["type": "item_completed", "item": ["type": "CommandExecution", "call_id": "a", "status": status]])
        }
        #expect(p.lastToolResults.first?.conflictingResults == true)
        #expect(p.lastToolResults.first?.callOutcome == .unknown)
        _ = p.events(fromLine: Data("{broken".utf8))
        #expect(p.lastToolResults.isEmpty)
        _ = parse(p, ["type": "function_call_output", "call_id": "a", "output": "unknown"])
        #expect(p.lastToolResults.first?.conflictingResults == true)
    }

    @Test func boundedEvidenceDoesNotGuessAnEvictedItemIdentity() {
        let tracker = CodexResultTracker(capacity: 2)
        for id in ["a", "b", "c"] { tracker.start(id) }
        let result = tracker.record(session: "s", payload: [:], item: ["id": "a", "status": "failed"], sourceKind: "item_completed", timestamp: 0)
        #expect(result.association == "unlinked" && !result.projectionEligible)
        #expect(result.outcome == .failed)
    }

    @Test func onlyStructuredTypedEvidenceDeterminesOutcome() {
        for row: [String: Any] in [["exit_code": true], ["exit_code": 1.5], ["success": 1], ["status": "completed"]] {
            #expect(CodexResultTracker.outcome(row).0 == .unknown)
        }
        #expect(CodexResultTracker.outcome(["status": "cancelled", "exit_code": 130]).0 == .cancelled)
        #expect(CodexResultTracker.outcome(["result": ["isError": true]]).0 == .failed)
    }
}
