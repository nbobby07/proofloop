import { describe, expect, it, vi } from "vitest";
import { getReport, getRun, challengeRun } from "../services/api";
import { runPayload, analyticsPayload } from "../services/validation";

describe("API trust boundaries", () => {
  it("rejects mismatched event identities", () => {
    expect(() =>
      runPayload({
        run_id: "run_a",
        target: "LedgerLite",
        source: "execution",
        status: "pending",
        events: [
          {
            event_id: "e1",
            run_id: "run_b",
            source: "execution",
            stage: "pending",
            event_type: "stage_started",
            severity: "info",
            timestamp: "2026-10-09T12:00:00Z",
            message: "started",
            metadata: {},
          },
        ],
      }),
    ).toThrow();
  });
  it("rejects impossible counts instead of showing misleading statistics", () => {
    expect(() =>
      analyticsPayload({
        source: "execution",
        run_count: 1,
        verified_count: 2,
        rejected_count: 0,
        failure_patterns: [],
      }),
    ).toThrow();
  });
  it("rejects unsafe run IDs before making a request", async () => {
    const network = vi.fn();
    vi.stubGlobal("fetch", network);
    expect(() => getRun("../../private")).toThrow();
    expect(network).not.toHaveBeenCalled();
  });
  it("does not leak provider responses or retry mutating requests", async () => {
    const network = vi
      .fn()
      .mockResolvedValue(
        new Response("private upstream error", { status: 500 }),
      );
    vi.stubGlobal("fetch", network);
    await expect(
      challengeRun("run_a", { max_challenges: 2, policy_ids: [] }),
    ).rejects.toThrow("HTTP 500");
    expect(network).toHaveBeenCalledTimes(1);
  });
  it("validates successful HTTP responses before accepting evidence", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({
              run_id: "run_a",
              source: "execution",
              status: "verified",
              summary: "ok",
              limitations: [],
              evidence: [
                {
                  artifact_id: "e1",
                  description: "receipt",
                  sha256: "invalid",
                },
              ],
            }),
          ),
        ),
    );
    await expect(getReport("run_a")).rejects.toThrow("does not match");
  });
});
