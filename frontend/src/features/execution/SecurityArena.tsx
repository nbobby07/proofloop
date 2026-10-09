import type { RunResponse, RunStatus, SecurityEvent } from "../../types";
import { StatusBadge } from "../../components/StatusBadge";
import { Icon } from "../../components/Icon";
import { labels } from "./lifecycle";
import { terminal } from "./lifecycle";

const stages: { label: string; states: RunStatus[] }[] = [
  { label: "Discover", states: ["discovering"] },
  { label: "Reproduce", states: ["reproducing"] },
  { label: "Patch", states: ["generating_patch", "applying_patch"] },
  { label: "Verify", states: ["verifying"] },
  { label: "Challenge", states: ["challenging"] },
  { label: "Retry", states: ["retrying"] },
];
function PipelineTimeline({
  run,
  events,
}: {
  run: RunResponse;
  events: SecurityEvent[];
}) {
  return (
    <section className="pipeline-card">
      <div className="section-heading">
        <div className="heading-with-icon">
          <Icon name="terminal" />
          <h2>Execution pipeline</h2>
        </div>
        <StatusBadge status={run.status} />
      </div>
      <ol className="pipeline-list">
        {stages.map((stage, i) => {
          const active = stage.states.includes(run.status);
          const completed = events.some(
            (e) =>
              stage.states.includes(e.stage) &&
              e.event_type === "stage_completed",
          );
          const seen = events.some((e) => stage.states.includes(e.stage));
          return (
            <li
              key={stage.label}
              className={active ? "active" : completed ? "complete" : ""}
            >
              <span className="stage-number">
                {completed && !active ? (
                  <Icon name="check" />
                ) : (
                  String(i + 1).padStart(2, "0")
                )}
              </span>
              <div>
                <strong>{stage.label}</strong>
                <small>
                  {active
                    ? "In progress"
                    : completed
                      ? "Recorded"
                      : seen
                        ? "Events recorded"
                        : terminal(run.status)
                          ? "Not recorded"
                          : "Pending"}
                </small>
              </div>
            </li>
          );
        })}
      </ol>
      <div className={`verdict verdict-${run.status}`}>
        <span className="verdict-label">Verdict</span>
        <strong>{labels[run.status]}</strong>
        <span>
          {run.status === "verified"
            ? "Passed the executed suite. See report for scope and limitations."
            : run.status === "rejected"
              ? "Required checks failed. Review the recorded evidence."
              : run.status === "inconclusive"
                ? "Required evidence is incomplete."
                : run.status === "error"
                  ? "Execution did not complete."
                  : "Awaiting independent verification."}
        </span>
      </div>
    </section>
  );
}
export function SecurityArena({
  run,
  events,
}: {
  run: RunResponse | null;
  events: SecurityEvent[];
}) {
  if (!run)
    return (
      <section className="panel run-empty">
        <span className="empty-icon">
          <Icon name="shield" size={26} />
        </span>
        <h2>No run selected</h2>
        <p>
          Start a verification run or open a saved run to inspect its attack,
          patch, and test evidence.
        </p>
      </section>
    );
  const attacks = events.filter(
    (e) =>
      ["baseline_reproduced", "challenge_proposed"].includes(e.event_type) ||
      e.stage === "challenging",
  );
  const defense = events.filter((e) =>
    ["patch_proposed", "patch_applied", "retry_scheduled"].includes(
      e.event_type,
    ),
  );
  return (
    <>
      <PipelineTimeline run={run} events={events} />
      <div className="arena-grid">
        <section className="team-panel red-team">
          <div className="team-heading">
            <span className="team-symbol">
              <Icon name="attack" />
            </span>
            <h2>Attack reproduction</h2>
            <span className="team-label">RED TEAM</span>
          </div>
          <div className="team-body">
            <div className="finding-heading">
              <span className="eyebrow">
                {run.finding?.id ?? "Vulnerability"}
              </span>
              {run.finding && (
                <span className={`badge severity-${run.finding.severity}`}>
                  {run.finding.severity}
                </span>
              )}
            </div>
            <h3 className="finding-title">
              {run.finding?.title ?? "Awaiting discovery"}
            </h3>
            <div className="request-trace">
              <div>
                <span className="avatar">A</span>
                <div>
                  <strong>Alice</strong>
                  <small>Authenticated principal</small>
                </div>
              </div>
              <div className="authorization-boundary">
                <span /> <Icon name="arrow" />
                <small>Ownership boundary</small>
              </div>
              <div>
                <Icon name="file" />
                <div>
                  <strong>Invoice #2001</strong>
                  <small>Owned by Bob</small>
                </div>
              </div>
            </div>
            <span className="trace-caption">
              LedgerLite authorization scenario
            </span>
            <div className="observation">
              <span>Baseline response</span>
              <div>
                <code className={run.baseline?.reproduced ? "danger-text" : ""}>
                  {run.baseline?.observed_status
                    ? `HTTP ${run.baseline.observed_status}`
                    : "Not recorded"}
                </code>
                <span className="observation-note">
                  {run.baseline
                    ? run.baseline.reproduced
                      ? "Vulnerability reproduced"
                      : "Not reproduced"
                    : "Awaiting evidence"}
                </span>
              </div>
            </div>
            <div className="team-events">
              {attacks.length ? (
                attacks.slice(-2).map((e) => (
                  <p key={e.event_id}>
                    <span className="dot" />
                    {e.message}
                  </p>
                ))
              ) : (
                <p className="empty-copy">
                  No attack or challenge events recorded.
                </p>
              )}
            </div>
          </div>
        </section>
        <section className="team-panel blue-team">
          <div className="team-heading">
            <span className="team-symbol">
              <Icon name="shield" />
            </span>
            <h2>Patch & remediation</h2>
            <span className="team-label">BLUE TEAM</span>
          </div>
          <div className="team-body">
            <div className="finding-heading">
              <span className="eyebrow">DEFENDER PROPOSAL</span>
              <span className="badge">
                {run.patch
                  ? `Attempt ${String(run.patch.attempt).padStart(2, "0")}`
                  : "Pending"}
              </span>
            </div>
            <h3 className="finding-title">
              {run.patch
                ? "Authorization patch proposed"
                : "Awaiting remediation"}
            </h3>
            <div className={`patch-summary ${run.patch ? "has-code" : ""}`}>
              <Icon name="code" size={22} />
              <div>
                <strong>
                  {run.patch ? "Code changes available" : "No patch generated"}
                </strong>
                <p>
                  {run.patch
                    ? "Review added and removed lines in the code changes tab."
                    : "The defender’s proposal will appear after generation."}
                </p>
              </div>
              {run.patch && (
                <pre className="patch-preview">
                  <code>
                    {run.patch.diff
                      .split("\n")
                      .filter(
                        (line) =>
                          line.startsWith("+") && !line.startsWith("+++"),
                      )
                      .slice(0, 2)
                      .join("\n") || "Unified diff available below"}
                  </code>
                </pre>
              )}
            </div>
            <div className="observation">
              <span>Patched response</span>
              <div>
                <code>Not recorded</code>
                <span className="observation-note">
                  Not included in current evidence
                </span>
              </div>
            </div>
            <div className="team-events">
              {defense.length ? (
                defense.slice(-2).map((e) => (
                  <p key={e.event_id}>
                    <span className="dot" />
                    {e.message}
                  </p>
                ))
              ) : (
                <p className="empty-copy">No patch or retry events recorded.</p>
              )}
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
