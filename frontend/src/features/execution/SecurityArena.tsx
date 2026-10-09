import { motion, useReducedMotion } from "motion/react";
import { motionTokens } from "../../components/motion";
import type {
  ReportResponse,
  RunResponse,
  RunStatus,
  SecurityEvent,
} from "../../types";
import { Icon } from "../../components/Icon";
import { labels } from "./lifecycle";
import { terminal } from "./lifecycle";

const stages: { label: string; states: RunStatus[] }[] = [
  { label: "Discover", states: ["discovering"] },
  { label: "Reproduce", states: ["reproducing"] },
  { label: "Patch", states: ["generating_patch", "applying_patch"] },
  { label: "Verify", states: ["verifying"] },
  { label: "Challenge", states: ["challenging"] },
  {
    label: "Report",
    states: ["verified", "rejected", "inconclusive", "error"],
  },
];
function PipelineTimeline({
  run,
  events,
  report,
}: {
  report: ReportResponse | null;
  run: RunResponse;
  events: SecurityEvent[];
}) {
  const reduced = useReducedMotion();
  // A terminal stage is completed when a fresh challenge invalidates that verdict.
  let cycleStart = 0;
  events.forEach((event, index) => {
    if (event.event_type === "stage_completed" && terminal(event.stage))
      cycleStart = index + 1;
  });
  const currentEvents = events.slice(cycleStart);
  return (
    <section className="pipeline-card">
      <div className="section-heading">
        <div className="heading-with-icon">
          <span className="section-index">01</span>
          <h2>Execution pipeline</h2>
        </div>
        <span className="pipeline-source">
          {run.source === "fixture"
            ? "ILLUSTRATIVE PIPELINE"
            : "BACKEND EXECUTION"}
        </span>
      </div>
      <ol className="pipeline-list">
        {stages.map((stage, i) => {
          const isReport = stage.label === "Report";
          const active =
            !isReport &&
            (stage.states.includes(run.status) ||
              (stage.label === "Patch" && run.status === "retrying"));
          const completed = isReport
            ? !!report
            : currentEvents.some(
                (e) =>
                  stage.states.includes(e.stage) &&
                  e.event_type === "stage_completed",
              );
          const seen = currentEvents.some((e) =>
            stage.states.includes(e.stage),
          );
          const historical =
            cycleStart > 0 &&
            events
              .slice(0, cycleStart)
              .some((e) => stage.states.includes(e.stage));
          return (
            <li
              key={stage.label}
              className={active ? "active" : completed ? "complete" : ""}
            >
              <motion.span
                className="stage-number"
                animate={{
                  backgroundColor: active ? "#27374a" : "#191e24",
                  borderColor: active ? "#8eafd3" : "#39434f",
                }}
                transition={{ duration: reduced ? 0 : motionTokens.state }}
              >
                {completed && !active ? (
                  <Icon name="check" />
                ) : (
                  String(i + 1).padStart(2, "0")
                )}
              </motion.span>
              <div>
                <strong>{stage.label}</strong>
                <small>
                  {active
                    ? "In progress"
                    : completed
                      ? "Recorded"
                      : isReport
                        ? run.source === "fixture"
                          ? "Preview only"
                          : terminal(run.status)
                            ? "Awaiting report"
                            : "Pending"
                        : historical && !seen
                          ? "Earlier cycle"
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
      <div
        className={`verdict verdict-${run.source === "fixture" ? "fixture" : run.status}`}
      >
        <span className="verdict-emblem">
          <Icon
            name={
              run.status === "verified" && run.source === "execution"
                ? "check"
                : "shield"
            }
            size={21}
          />
        </span>
        <div className="verdict-state">
          <span className="verdict-label">
            {run.source === "fixture"
              ? "ILLUSTRATIVE VERDICT"
              : "INDEPENDENT VERDICT"}
          </span>
          <motion.strong
            key={run.status}
            initial={reduced ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: reduced ? 0 : motionTokens.micro }}
            role="status"
          >
            {run.source === "fixture"
              ? `Preview · ${labels[run.status]}`
              : labels[run.status]}
          </motion.strong>
        </div>
        <span>
          {run.source === "fixture"
            ? "Illustrative state. No independent verification has executed."
            : run.status === "verified"
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
  report = null,
}: {
  report?: ReportResponse | null;
  run: RunResponse | null;
  events: SecurityEvent[];
}) {
  const reduced = useReducedMotion();
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
  const attacks = events.filter((e) =>
    ["baseline_reproduced", "challenge_proposed"].includes(e.event_type),
  );
  const defense = events.filter((e) =>
    ["patch_proposed", "patch_applied", "retry_scheduled"].includes(
      e.event_type,
    ),
  );
  return (
    <>
      <PipelineTimeline run={run} events={events} report={report} />
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
            <motion.div
              className={`request-trace ${run.baseline?.reproduced ? "boundary-reproduced" : ""}`}
              animate={{
                borderColor: run.baseline?.reproduced ? "#7c4846" : "#343d48",
              }}
              transition={{ duration: reduced ? 0 : motionTokens.state }}
            >
              <div>
                <span className="avatar">
                  <Icon name="fingerprint" />
                </span>
                <div>
                  <strong>Principal</strong>
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
                  <strong>Protected object</strong>
                  <small>Other owner</small>
                </div>
              </div>
            </motion.div>
            <span className="trace-caption">
              {run.target} ownership model · schematic
            </span>
            <div className="observation">
              <span>Recorded baseline</span>
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
            <motion.div
              key={run.patch?.attempt ?? "waiting"}
              className={`patch-summary ${run.patch ? "has-code" : ""}`}
              initial={reduced ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: reduced ? 0 : motionTokens.panel }}
            >
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
            </motion.div>
            <div className="observation">
              <span>Proposal status</span>
              <div>
                <code>{run.patch ? "Diff recorded" : "Not recorded"}</code>
                <span className="observation-note">
                  Independent verification required
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
