import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useRun } from "../features/execution/useRun";
import * as api from "../services/api";
import type { ReportResponse, RunResponse, SecurityEvent } from "../types";

vi.mock("../services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/api")>()),
  getRun: vi.fn(),
  getRunEvents: vi.fn(),
  getReport: vi.fn(),
  createRun: vi.fn(),
  challengeRun: vi.fn(),
}));
const runDouble: RunResponse = {
  run_id: "run_unit",
  target: "LedgerLite",
  source: "execution",
  status: "verified",
  events: [],
  baseline: { reproduced: true, observed_status: 200 },
  patch: { attempt: 1, diff: "Unit transport double; no applied patch" },
  verification: {
    security_passed: 1,
    security_total: 1,
    functional_passed: 1,
    functional_total: 1,
    adversarial_passed: 1,
    adversarial_total: 1,
  },
};
const completion: SecurityEvent = {
  event_id: "done_old",
  run_id: "run_unit",
  source: "execution",
  stage: "verified",
  event_type: "run_completed",
  severity: "info",
  timestamp: "2026-10-09T12:00:00Z",
  message: "Unit transport double; no security execution",
  metadata: {},
};
const reportDouble: ReportResponse = {
  run_id: "run_unit",
  source: "execution",
  status: "verified",
  summary: "Unit transport double",
  limitations: [],
  evidence: [],
};

describe("run lifecycle", () => {
  beforeEach(() => {
    vi.mocked(api.getRun).mockReset().mockResolvedValue(runDouble);
    vi.mocked(api.getRunEvents)
      .mockReset()
      .mockResolvedValue({
        run_id: "run_unit",
        source: "execution",
        events: [completion],
        next_cursor: null,
      });
    vi.mocked(api.getReport).mockReset().mockResolvedValue(reportDouble);
    vi.mocked(api.createRun).mockReset();
    vi.mocked(api.challengeRun)
      .mockReset()
      .mockResolvedValue({
        run_id: "run_unit",
        source: "execution",
        status: "challenging",
      });
  });
  it("invalidates prior verification after an accepted challenge even if a stale terminal snapshot arrives", async () => {
    const { result } = renderHook(() => useRun(true));
    act(() => result.current.open("run_unit"));
    await waitFor(() => expect(result.current.report).toEqual(reportDouble));
    await act(async () => result.current.challenge());
    await waitFor(() => expect(api.getRun).toHaveBeenCalledTimes(2));
    expect(result.current.run?.status).toBe("challenging");
    expect(result.current.run?.verification).toBeNull();
    expect(result.current.report).toBeNull();
    expect(api.getReport).toHaveBeenCalledTimes(1);
  });
  it("does not submit a challenge for an execution error without reproduced baseline and patch", async () => {
    vi.mocked(api.getRun).mockResolvedValue({
      ...runDouble,
      status: "error",
      baseline: null,
      patch: null,
      verification: null,
    });
    const { result } = renderHook(() => useRun(true));
    act(() => result.current.open("run_unit"));
    await waitFor(() => expect(result.current.run?.status).toBe("error"));
    await act(async () => result.current.challenge());
    expect(api.challengeRun).not.toHaveBeenCalled();
  });
  it("drains short paginated pages, deduplicates IDs and preserves delivery order", async () => {
    vi.mocked(api.getRunEvents)
      .mockResolvedValueOnce({
        run_id: "run_unit",
        source: "execution",
        events: [
          {
            ...completion,
            event_id: "first",
            timestamp: "2026-10-09T12:00:02Z",
          },
        ],
        next_cursor: "page_1",
      })
      .mockResolvedValueOnce({
        run_id: "run_unit",
        source: "execution",
        events: [
          { ...completion, event_id: "first" },
          {
            ...completion,
            event_id: "second",
            timestamp: "2026-10-09T12:00:01Z",
          },
        ],
        next_cursor: "page_2",
      })
      .mockResolvedValueOnce({
        run_id: "run_unit",
        source: "execution",
        events: [],
        next_cursor: "page_2",
      });
    const { result } = renderHook(() => useRun(true));
    act(() => result.current.open("run_unit"));
    await waitFor(() => expect(result.current.report).toBeTruthy());
    expect(result.current.events.map((e) => e.event_id)).toEqual([
      "first",
      "second",
    ]);
    expect(
      vi.mocked(api.getRunEvents).mock.calls.map((call) => call[1]),
    ).toEqual([undefined, "page_1", "page_2"]);
  });
  it("rejects fixture data returned by a live endpoint", async () => {
    vi.mocked(api.getRun).mockResolvedValue({
      ...runDouble,
      source: "fixture",
    });
    const { result } = renderHook(() => useRun(true));
    act(() => result.current.open("run_unit"));
    await waitFor(() => expect(result.current.error).toContain("fixture"));
    expect(result.current.run).toBeNull();
    expect(result.current.history).toEqual([]);
  });
  it("cancels an in-flight creation and releases busy state when preview mode is selected", async () => {
    vi.mocked(api.createRun).mockImplementation(
      (_body, signal) =>
        new Promise((_resolve, reject) =>
          signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          ),
        ),
    );
    const { result, rerender } = renderHook(({ enabled }) => useRun(enabled), {
      initialProps: { enabled: true },
    });
    act(() => {
      void result.current.start();
    });
    expect(result.current.busy).toBe(true);
    rerender({ enabled: false });
    await waitFor(() => expect(result.current.busy).toBe(false));
    expect(result.current.error).toBeNull();
    expect(result.current.run).toBeNull();
  });
});
