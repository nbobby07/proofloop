import type { RunStatus, SecurityEvent } from "../../types";

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
