import type { RunStatus } from "../types";
import { labels } from "../features/execution/lifecycle";

export function StatusBadge({ status }: { status?: RunStatus }) {
  return (
    <span className={`badge status-${status ?? "pending"}`}>
      <span className="dot" />
      {status ? labels[status] : "Awaiting run"}
    </span>
  );
}
export function SourceBadge({ fixture }: { fixture: boolean }) {
  return (
    <span className={`badge ${fixture ? "fixture" : "execution"}`}>
      {fixture ? "FIXTURE · no execution" : "LIVE · execution only"}
    </span>
  );
}
