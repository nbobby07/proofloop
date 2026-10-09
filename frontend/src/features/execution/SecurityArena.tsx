import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { ReportResponse, RunResponse, SecurityEvent } from "../../types";
import { Icon } from "../../components/Icon";
import { motionTokens } from "../../components/motion";
import { BriefingPanel } from "../briefing/BriefingPanel";
import { RunControls } from "./RunControls";
import { terminal } from "./lifecycle";
import {
  activityCopy,
  attemptHistory,
  checkCounts,
  currentPhase,
  issueDescription,
  phases,
  resultCopy,
} from "../investigation/model";
import type { EvidenceView } from "../investigation/model";

export function SecurityArena({
  run,
  events,
  report = null,
  busy = false,
  requestingChallenge = false,
  inspect = () => {},
  challenge = () => {},
  useLive = () => {},
  refresh = () => {},
}: {
  run: RunResponse | null;
  events: SecurityEvent[];
  report?: ReportResponse | null;
  busy?: boolean;
  requestingChallenge?: boolean;
  inspect?: (view: EvidenceView) => void;
  challenge?: () => void;
  useLive?: () => void;
  refresh?: () => void;
}) {
  const reduced = useReducedMotion();
  const [briefingOpen, setBriefingOpen] = useState(false);
  if (!run) return null;
  const fixture = run.source === "fixture";
  const finished = terminal(run.status);
  const phase = currentPhase(run, events);
  const attempts = attemptHistory(run, events);
  const counts = checkCounts(run);
  const copy = resultCopy(run, events);
  const currentPatchPassed =
    !!run.patch &&
    events.some(
      (event) =>
        event.source === "execution" &&
        event.stage === "verifying" &&
        event.event_type === "test_completed" &&
        event.metadata?.attempt === run.patch?.attempt &&
        event.metadata?.executed === true &&
        event.metadata?.outcome === "pass",
    );
  const completed = [
    !fixture && run.baseline?.reproduced === true,
    !fixture && currentPatchPassed,
    !fixture && run.status === "verified",
  ];
  const cycleStart = events.reduce(
    (start, event, index) =>
      ["run_completed", "run_failed"].includes(event.event_type)
        ? index + 1
        : start,
    0,
  );
  const latest = requestingChallenge
    ? undefined
    : [...events.slice(cycleStart)]
        .reverse()
        .find((event) =>
          [
            "baseline_reproduced",
            "patch_proposed",
            "test_completed",
            "retry_scheduled",
            "challenge_proposed",
            "finding_discovered",
          ].includes(event.event_type),
        );
  const activity = !finished
    ? activityCopy[run.status as keyof typeof activityCopy]
    : null;
  return (
    <>
      <ol
        className={`investigation-phases ${finished ? "phases-finished" : ""}`}
        aria-label="Investigation progress"
      >
        {phases.map((label, index) => (
          <li
            key={label}
            className={
              !finished && index === phase
                ? "phase-current"
                : completed[index]
                  ? "phase-recorded"
                  : ""
            }
            aria-current={!finished && index === phase ? "step" : undefined}
          >
            <span className="phase-number">
              {completed[index] && index !== (!finished ? phase : -1) ? (
                <Icon name="check" />
              ) : (
                index + 1
              )}
            </span>
            <div>
              <strong>{["Find", "Fix", "Prove"][index]}</strong>
              <span>{label}</span>
            </div>
          </li>
        ))}
      </ol>
      {finished ? (
        <article className={`outcome-story outcome-${copy.tone}`}>
          <div className="outcome-label">
            <span className="outcome-seal">
              <Icon
                name={
                  copy.tone === "pass"
                    ? "check"
                    : copy.tone === "fail"
                      ? "info"
                      : "shield"
                }
                size={21}
              />
            </span>
            <span>{copy.label}</span>
            {!fixture && (
              <span className="result-source">Independent verification</span>
            )}
          </div>
          <motion.div
            key={run.status}
            role="status"
            aria-live="polite"
            aria-atomic="true"
            initial={reduced ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: reduced ? 0 : motionTokens.state }}
          >
            <h1 className="outcome-title">{copy.title}</h1>
            <p className="outcome-description">{copy.description}</p>
          </motion.div>
          <RunControls
            run={run}
            busy={busy}
            challenge={challenge}
            inspect={inspect}
            useLive={useLive}
            refresh={refresh}
          />
        </article>
      ) : (
        <article className="activity-story">
          <div className="outcome-label">
            <span className="activity-mark">
              <Icon name="arena" size={22} />
            </span>
            <span>
              {requestingChallenge
                ? "Request pending"
                : `In progress · ${["Find", "Fix", "Prove"][phase]}`}
            </span>
          </div>
          <motion.div
            key={run.status}
            role="status"
            aria-live="polite"
            aria-atomic="true"
            initial={reduced ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: reduced ? 0 : motionTokens.panel }}
          >
            <h1 className="outcome-title">
              {requestingChallenge
                ? "Requesting a fresh challenge."
                : activity?.title}
            </h1>
            <p className="outcome-description">
              {requestingChallenge
                ? "The previous result is withheld while the backend accepts the request. No new verdict is available yet."
                : activity?.description}
            </p>
          </motion.div>
          {latest && (
            <div className="latest-evidence">
              <span>Latest recorded update</span>
              <p>{latest.message}</p>
            </div>
          )}
          <button className="text-button" onClick={() => inspect("audit")}>
            Follow the audit trail <Icon name="arrow" />
          </button>
        </article>
      )}
      {(run.baseline || finished) && (
        <section
          className="evidence-comparison"
          aria-label="Before and after evidence"
        >
          <div className="comparison-before">
            <span className="section-label">Before</span>
            <h2>
              {run.baseline?.reproduced
                ? "The original failure"
                : "Original application"}
            </h2>
            <p>{issueDescription(run)}</p>
            <span className="comparison-footnote">
              {run.baseline?.observed_status ? (
                <>
                  Recorded response{" "}
                  <code>HTTP {run.baseline.observed_status}</code>
                </>
              ) : (
                "Original HTTP response unavailable"
              )}
            </span>
          </div>
          <div
            className={`comparison-after ${finished && run.status === "verified" && !fixture ? "comparison-passed" : ""}`}
          >
            <span className="section-label">{finished ? "After" : "Next"}</span>
            <h2>
              {fixture
                ? "Illustrative patch outcome"
                : run.status === "verified"
                  ? "The fix earned a passing verdict"
                  : run.status === "rejected"
                    ? "The patch was not accepted"
                    : "Independent evidence required"}
            </h2>
            <p>
              {fixture
                ? "The sample shows a proposed ownership check and illustrative test counts."
                : run.status === "verified"
                  ? "The current patch passed the required verification. Passing is limited to the executed suite."
                  : run.status === "rejected"
                    ? "Required checks failed. Review the outcomes before trusting this proposal."
                    : "A proposed patch is not proof. Completed independent checks determine the result."}
            </p>
            <button className="text-button" onClick={() => inspect("results")}>
              {counts
                ? `${counts.passed} / ${counts.total} ${fixture ? "illustrative" : "recorded passing"} checks`
                : "View test evidence"}
              <Icon name="arrow" />
            </button>
          </div>
        </section>
      )}
      {attempts.length > 0 && (
        <section className="attempt-story">
          <div className="section-intro">
            <h2>How the fix evolved</h2>
            <button className="text-button" onClick={() => inspect("results")}>
              Inspect test results <Icon name="arrow" />
            </button>
          </div>
          <ol className="attempt-sequence" aria-label="Patch attempt history">
            {attempts.map((item) => (
              <li key={item.attempt} className={`attempt-${item.tone}`}>
                <span className="attempt-marker">
                  <Icon
                    name={
                      item.tone === "pass"
                        ? "check"
                        : item.tone === "fail"
                          ? "info"
                          : "code"
                    }
                  />
                </span>
                <div>
                  <span>Attempt {item.attempt}</span>
                  <strong>{item.label}</strong>
                </div>
              </li>
            ))}
          </ol>
          <p className="fine-print">
            Only recorded attempts are shown. Earlier failures remain in the
            audit trail.
          </p>
        </section>
      )}
      {finished && (
        <p className="scope-note">
          <Icon name="shield" />
          {fixture
            ? "Preview evidence is illustrative and cannot establish a security verdict."
            : "This verdict applies to the current patch and frozen executed suite. It does not prove universal security."}
        </p>
      )}
      {report && (
        <div className="briefing-disclosure">
          <button
            className="text-button"
            aria-expanded={briefingOpen}
            onClick={() => setBriefingOpen((value) => !value)}
          >
            <Icon name="volume" />
            {briefingOpen
              ? "Close incident briefing"
              : "Listen to the incident briefing"}
          </button>
          {briefingOpen && (
            <BriefingPanel key={JSON.stringify(report)} report={report} />
          )}
        </div>
      )}
    </>
  );
}
