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
  it("emphasizes the fresh challenge and does not reuse an old completion as current activity", () => {
    render(
      <SecurityArena
        run={run}
        events={[
          event("old-pass", {
            message: "Old passing round",
            metadata: { attempt: 2, executed: true, outcome: "pass" },
          }),
          event("old-completion", {
            stage: "verified",
            event_type: "run_completed",
          }),
        ]}
      />,
    );
    expect(
      screen.getByRole("heading", {
        name: "Putting the fix through fresh challenges.",
      }),
    ).toBeTruthy();
    expect(screen.queryByText("Old passing round")).toBeNull();
    const progress = screen.getByRole("list", {
      name: "Investigation progress",
    });
    expect(
      within(progress)
        .getByText("Prove")
        .closest("li")
        ?.getAttribute("aria-current"),
    ).toBe("step");
    expect(
      screen.queryByRole("button", { name: "Challenge this fix" }),
    ).toBeNull();
  });
  it("does not turn all-passing counts into a verified verdict when the backend says incomplete", () => {
    render(
      <SecurityArena
        run={{
          ...run,
          status: "inconclusive",
          verification: {
            security_passed: 6,
            security_total: 6,
            functional_passed: 22,
            functional_total: 22,
            adversarial_passed: 16,
            adversarial_total: 16,
          },
        }}
        events={[]}
      />,
    );
    expect(
      screen.getByRole("heading", {
        name: "There isn’t enough evidence for a verdict.",
      }),
    ).toBeTruthy();
    expect(screen.queryByText("Verified")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Inspect recorded evidence" }),
    ).toBeTruthy();
  });
  it("uses the live verdict and actual counts for the result headline and next action", () => {
    render(
      <SecurityArena
        run={{
          ...run,
          status: "verified",
          verification: {
            security_passed: 6,
            security_total: 6,
            functional_passed: 22,
            functional_total: 22,
            adversarial_passed: 16,
            adversarial_total: 16,
          },
        }}
        events={[]}
      />,
    );
    expect(
      screen.getByRole("heading", {
        name: "Patch verified against 44 executed checks.",
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Challenge this fix" }),
    ).toBeTruthy();
    expect(screen.queryByText("HTTP 403")).toBeNull();
    expect(screen.getByText("HTTP 200")).toBeTruthy();
  });
});
