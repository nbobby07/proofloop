import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Welcome } from "../features/investigation/Welcome";
import { WorkspaceEvidence } from "../features/investigation/WorkspaceEvidence";
import { resultCopy } from "../features/investigation/model";
import type { RunResponse } from "../types";

const run: RunResponse = { run_id: "run_workspace", target: "LedgerLite Workspace", source: "execution", status: "inconclusive", finding: null, baseline: null, patch: null, verification: null, events: [] };
afterEach(() => vi.unstubAllGlobals());

it("keeps Classic local and sends the explicit Workspace cloud selection", () => {
  const start = vi.fn();
  render(<Welcome start={start} history={() => {}} connection="connected" busy={false} opening={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Run security verification" }));
  expect(start).toHaveBeenLastCalledWith("LedgerLite", "local");
  fireEvent.change(screen.getByLabelText("Application"), { target: { value: "LedgerLite Workspace" } });
  fireEvent.change(screen.getByLabelText("Verification location"), { target: { value: "local_akash" } });
  fireEvent.click(screen.getByRole("button", { name: "Run security verification" }));
  expect(start).toHaveBeenLastCalledWith("LedgerLite Workspace", "local_akash");
});

it("rejects another run's execution details", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ run_id: "different", source: "execution", entries: [] }) }));
  render(<WorkspaceEvidence run={run} />);
  await waitFor(() => expect(screen.getByText(/Execution details are unavailable/)).toBeTruthy());
  expect(screen.queryByText(/checks passed/)).toBeNull();
});

it("describes a clean audit without inventing a verified patch", () => {
  const copy = resultCopy(run, [{ event_id: "event_1", run_id: run.run_id, stage: "inconclusive", event_type: "run_completed", source: "execution", severity: "info", timestamp: new Date().toISOString(), message: "Run finished: inconclusive. Reason: no_reproducible_finding.", metadata: {} }]);
  expect(copy.title).toBe("No reproducible vulnerability found.");
  expect(copy.label).toBe("Audit complete");
});
