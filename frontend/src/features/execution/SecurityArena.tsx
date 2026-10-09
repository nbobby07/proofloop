import type { RunResponse, RunStatus, SecurityEvent } from "../../types";
import { StatusBadge } from "../../components/StatusBadge";
import { labels } from "./lifecycle";

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
  run: RunResponse | null;
  events: SecurityEvent[];
}) {
  return (
    <section className="pipeline-card">
      <div className="section-heading">
        <span className="eyebrow">Independent execution</span>
        <StatusBadge status={run?.status} />
      </div>
      <h2>The proof loop</h2>
      <p className="support">Every verdict needs evidence.</p>
      <ol className="pipeline-list">
        {stages.map((stage, i) => {
          const active = !!run && stage.states.includes(run.status);
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
                {completed && !active ? "✓" : String(i + 1).padStart(2, "0")}
              </span>
              <div>
                <strong>{stage.label}</strong>
                <small>
                  {active
                    ? "In progress"
                    : completed
                      ? "Completion recorded"
                      : seen
                        ? "Events recorded"
                        : "No evidence yet"}
                </small>
              </div>
              <span className="stage-indicator" />
            </li>
          );
        })}
      </ol>
      <div className={`verdict verdict-${run?.status ?? "pending"}`}>
        <span className="eyebrow">Backend verdict</span>
        <strong>{run ? labels[run.status] : "Waiting for execution"}</strong>
        <p>
          {run?.status === "verified"
            ? "Passed the executed suite. Scope and limitations remain in the report."
            : run?.status === "rejected"
              ? "Required executed checks failed. Inspect the evidence below."
              : run?.status === "inconclusive"
                ? "Required evidence is incomplete. This is not a passing result."
                : run?.status === "error"
                  ? "Execution could not complete. No passing verdict is established."
                  : "Agents propose. Independent checks decide."}
        </p>
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
    <div className="arena-grid">
      <section className="team-panel red-team">
        <div className="team-heading">
          <span className="team-symbol">↗</span>
          <div>
            <p className="eyebrow">Red team</p>
            <h2>Challenge the boundary.</h2>
          </div>
          <span className="team-label">ATTACK</span>
        </div>
        <p className="support">Controlled reproduction & adversarial cases</p>
        <div className="finding-card">
          <span className="eyebrow">
            {run?.finding?.id ?? "Finding pending"}
          </span>
          <h3>{run?.finding?.title ?? "Awaiting vulnerability discovery"}</h3>
          <span className="badge danger">
            {run?.finding?.severity ?? "No severity recorded"}
          </span>
        </div>
        <div className="boundary-demo">
          <div>
            <span className="avatar">A</span>
            <strong>Alice</strong>
            <small>Authenticated user</small>
          </div>
          <span className="boundary-arrow">→</span>
          <div>
            <span className="invoice">#2001</span>
            <strong>Bob’s invoice</strong>
            <small>LedgerLite demo scenario</small>
          </div>
        </div>
        <div className="observation">
          <span>Baseline response</span>
          <strong>
            {run?.baseline?.observed_status
              ? `HTTP ${run.baseline.observed_status}`
              : "Not recorded"}
          </strong>
          <small>
            {run?.baseline
              ? run.baseline.reproduced
                ? "Vulnerability reproduced"
                : "Not reproduced"
              : "Awaiting actual baseline evidence"}
          </small>
        </div>
        <div className="team-events">
          {attacks.length ? (
            attacks.slice(-3).map((e) => (
              <p key={e.event_id}>
                <span>↗</span>
                {e.message}
              </p>
            ))
          ) : (
            <p className="empty-copy">
              Attack and challenge evidence will appear here.
            </p>
          )}
        </div>
      </section>
      <PipelineTimeline run={run} events={events} />
      <section className="team-panel blue-team">
        <div className="team-heading">
          <span className="team-symbol">⌘</span>
          <div>
            <p className="eyebrow">Blue team</p>
            <h2>Defend with evidence.</h2>
          </div>
          <span className="team-label">DEFEND</span>
        </div>
        <p className="support">Remediation proposals & verification feedback</p>
        <div className="patch-card">
          <span className="eyebrow">Remediation</span>
          <div className="attempt-number">
            {run?.patch ? String(run.patch.attempt).padStart(2, "0") : "—"}
            <small>patch attempt</small>
          </div>
          <p>
            {run?.patch
              ? "A patch proposal is available. Inspect its exact changes below."
              : "The defender has not supplied a patch."}
          </p>
        </div>
        <div className="observation">
          <span>Patched HTTP response</span>
          <strong>Not supplied</strong>
          <small>
            The current contract provides baseline HTTP status only.
          </small>
        </div>
        <div className="team-events">
          {defense.length ? (
            defense.slice(-3).map((e) => (
              <p key={e.event_id}>
                <span>⌘</span>
                {e.message}
              </p>
            ))
          ) : (
            <p className="empty-copy">
              Patch and retry feedback will appear here.
            </p>
          )}
        </div>
        <div className="trust-note">
          <span>◇</span> A generated patch is a proposal until independently
          verified.
        </div>
      </section>
    </div>
  );
}
