import type { RunResponse, RunStatus, SecurityEvent } from "../../types";

export const labels: Record<RunStatus, string> = {
  pending: "Queued",
  discovering: "Discovering",
  reproducing: "Reproducing",
  generating_patch: "Generating patch",
  applying_patch: "Applying patch",
  verifying: "Verifying",
  challenging: "Challenging",
  retrying: "Retrying",
  verified: "Verified",
  rejected: "Rejected",
  inconclusive: "Inconclusive",
  error: "Execution error",
};
export const terminal = (status: RunStatus) =>
  ["verified", "rejected", "inconclusive", "error"].includes(status);
export function mergeEvents(
  existing: SecurityEvent[],
  incoming: SecurityEvent[],
) {
  const seen = new Set(existing.map((e) => e.event_id));
  return [
    ...existing,
    ...incoming.filter((e) => !seen.has(e.event_id) && !!seen.add(e.event_id)),
  ];
}

export const canChallenge = (run: RunResponse | null) =>
  !!run &&
  ["verified", "rejected", "inconclusive"].includes(run.status) &&
  !!run.patch &&
  run.baseline?.reproduced === true;

// Presentation labels for recorded rounds; these cannot assign a run verdict.
export function recordedOutcome(event: SecurityEvent) {
  if (event.source === "fixture")
    return { label: "Preview", tone: "incomplete" };
  if (event.metadata?.executed === false)
    return { label: "Not executed", tone: "incomplete" };
  if (event.metadata?.executed === true && event.metadata?.outcome === "pass")
    return { label: "Passed", tone: "pass" };
  if (event.metadata?.executed === true && event.metadata?.outcome === "fail")
    return { label: "Failed", tone: "fail" };
  return { label: "Incomplete / unavailable", tone: "incomplete" };
}
