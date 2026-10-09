import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Dashboard } from "../pages/Dashboard";
import { IncidentBriefingPlayer } from "../features/briefing/IncidentBriefingPlayer";
import { saveSelection } from "../features/execution/session";
import * as api from "../services/api";
import type { RunResponse, SecurityEvent } from "../types";
vi.mock("../services/api", async (original) => ({
  ...(await original<typeof import("../services/api")>()),
  getHealth: vi.fn(),
  getRun: vi.fn(),
  getRunEvents: vi.fn(),
  getReport: vi.fn(),
  challengeRun: vi.fn(),
}));
const run: RunResponse = {
  run_id: "run_ui_double",
  source: "execution",
  target: "LedgerLite",
  status: "verified",
  baseline: { reproduced: true, observed_status: 200 },
  patch: { attempt: 1, diff: "@@ -1 +1 @@\n-old\n+new" },
  verification: {
    security_passed: 1,
    security_total: 1,
    functional_passed: 1,
    functional_total: 1,
    adversarial_passed: 1,
    adversarial_total: 1,
  },
  events: [],
};
const oldEvent: SecurityEvent = {
  run_id: run.run_id,
  event_id: "old_completion",
  source: "execution",
  event_type: "run_completed",
  stage: "verified",
  severity: "info",
  message: "Explicit UI transport double, no security execution",
  timestamp: "2026-10-09T20:00:00Z",
  metadata: {},
};
describe("investigation trust boundaries", () => {
  beforeEach(() => {
    vi.mocked(api.getHealth).mockResolvedValue({
      status: "ok",
      service: "proofloop",
    });
    vi.mocked(api.getRun).mockResolvedValue(run);
    vi.mocked(api.getRunEvents).mockResolvedValue({
      run_id: run.run_id,
      source: "execution",
      events: [oldEvent],
      next_cursor: null,
    });
    vi.mocked(api.getReport).mockResolvedValue({
      run_id: run.run_id,
      source: "execution",
      status: "verified",
      summary: "UI test report",
      evidence: [],
      limitations: [],
    });
  });
  it("withholds the result in overview, presentation and history while a challenge request is unresolved", async () => {
    let reject!: (reason: Error) => void;
    vi.mocked(api.challengeRun).mockImplementation(
      () =>
        new Promise((_resolve, rejectPromise) => {
          reject = rejectPromise;
        }),
    );
    saveSelection("run", run.run_id);
    const user = userEvent.setup();
    render(<Dashboard />);
    await screen.findByRole("heading", {
      name: "Patch verified against 3 executed checks.",
    });
    await user.click(screen.getByRole("button", { name: "Presentation mode" }));
    await user.click(
      screen.getByRole("button", { name: "Challenge this fix" }),
    );
    expect(
      screen.getByRole("heading", { name: "Requesting a fresh challenge." }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("heading", { name: /Patch verified against/ }),
    ).toBeNull();
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "History" }));
    expect(screen.queryByText("Verified")).toBeNull();
    expect(screen.getByText("Challenging")).toBeTruthy();
    await act(async () =>
      reject(new Error("Request rejected by test transport")),
    );
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "Request rejected",
      ),
    );
    await user.click(screen.getByRole("button", { name: "Verification" }));
    expect(
      screen.getByRole("heading", {
        name: "Patch verified against 3 executed checks.",
      }),
    ).toBeTruthy();
  });
  it("pauses detached audio when its report-bound player is invalidated", () => {
    const pause = vi
      .spyOn(HTMLMediaElement.prototype, "pause")
      .mockImplementation(() => {});
    const mounted = render(
      <IncidentBriefingPlayer
        audio={{
          runId: "run_ui_double",
          url: "/unit-audio.mp3",
          transcript: "Explicit media test double",
          evidenceDigest: "unit",
        }}
      />,
    );
    mounted.unmount();
    expect(pause).toHaveBeenCalledTimes(1);
    pause.mockRestore();
  });
});
