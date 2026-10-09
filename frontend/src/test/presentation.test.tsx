import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tooltip } from "radix-ui";
import type { RunResponse, SecurityEvent } from "../types";
import { SecurityArena } from "../features/execution/SecurityArena";
import { EvidenceReport } from "../features/evidence/EvidenceReport";
import { recordedOutcome } from "../features/execution/lifecycle";

const event = (id: string, changes: Partial<SecurityEvent>): SecurityEvent => ({
  event_id: id,
  run_id: "run_ui",
  timestamp: "2026-10-09T20:00:00Z",
  source: "execution",
  stage: "verifying",
  event_type: "test_completed",
  severity: "info",
  message: "Explicit UI test double; no security execution",
  metadata: {},
  ...changes,
});
const run: RunResponse = {
  run_id: "run_ui",
  target: "LedgerLite",
  source: "execution",
  status: "challenging",
  baseline: { reproduced: true, observed_status: 200 },
  patch: { attempt: 2, diff: "@@ -1 +1 @@\n-old\n+new" },
  verification: null,
};

describe("evidence presentation boundaries", () => {
  it("requires explicit execution and a passing outcome to label a recorded round Passed", () => {
    expect(
      recordedOutcome(event("missing", { metadata: { outcome: "pass" } })).tone,
    ).toBe("incomplete");
    expect(
      recordedOutcome(
        event("skipped", { metadata: { outcome: "pass", executed: false } }),
      ).label,
    ).toBe("Not executed");
    expect(
      recordedOutcome(
        event("fixture", {
          source: "fixture",
          metadata: { outcome: "pass", executed: true },
        }),
      ).label,
    ).toBe("Preview");
    expect(
      recordedOutcome(
        event("passing", { metadata: { outcome: "pass", executed: true } }),
      ).label,
    ).toBe("Passed");
  });
  it("keeps a failed first attempt visible beside a later passing round", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip.Provider>
        <EvidenceReport
          run={run}
          report={null}
          reportError={null}
          fixture={false}
          events={[
            event("first", {
              message: "Attempt one rejected",
              metadata: { attempt: 1, outcome: "fail", executed: true },
            }),
            event("second", {
              message: "Attempt two recorded pass",
              metadata: { attempt: 2, outcome: "pass", executed: true },
            }),
          ]}
        />
      </Tooltip.Provider>,
    );
    await user.click(screen.getByText("Recorded verification rounds"));
    expect(screen.getByText("Failed")).toBeTruthy();
    expect(screen.getByText("Passed")).toBeTruthy();
    expect(screen.getByText("Attempt 01")).toBeTruthy();
    expect(screen.getByText("Attempt one rejected")).toBeTruthy();
    expect(screen.getByText(/Previous counts cleared/)).toBeTruthy();
    expect(screen.queryByText("Recorded passing")).toBeNull();
  });
  it("marks previous cycle stages historical while a new challenge is active", () => {
    render(
      <SecurityArena
        run={run}
        events={[
          event("old-verify", { event_type: "stage_completed" }),
          event("invalidate", {
            stage: "verified",
            event_type: "stage_completed",
          }),
          event("new-challenge", {
            stage: "challenging",
            event_type: "stage_started",
          }),
        ]}
      />,
    );
    const pipeline = screen
      .getByRole("heading", { name: "Execution pipeline" })
      .closest("section")!;
    expect(
      within(pipeline).getAllByText("Earlier cycle").length,
    ).toBeGreaterThan(0);
    expect(within(pipeline).getByRole("status").textContent).toBe(
      "Challenging",
    );
    expect(within(pipeline).queryByText("Verified")).toBeNull();
  });
  it("retains the diff filter when evidence tabs switch and keeps exact code selectable", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip.Provider>
        <EvidenceReport
          run={run}
          report={null}
          reportError={null}
          fixture={false}
        />
      </Tooltip.Provider>,
    );
    await user.click(screen.getByRole("tab", { name: "Code changes" }));
    await user.click(screen.getByRole("checkbox", { name: "Changes only" }));
    await user.click(screen.getByRole("tab", { name: "Verification" }));
    await user.click(screen.getByRole("tab", { name: "Code changes" }));
    expect(
      (
        screen.getByRole("checkbox", {
          name: "Changes only",
        }) as HTMLInputElement
      ).checked,
    ).toBe(true);
    expect(screen.getByLabelText("Patch code changes").textContent).toContain(
      "+new",
    );
  });
});
