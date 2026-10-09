import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { motionTokens } from "../../components/motion";
import { RecordedRounds } from "../execution/RecordedRounds";
import { labels } from "../execution/lifecycle";
import { Tooltip } from "radix-ui";
import type { ReportResponse, RunResponse, SecurityEvent } from "../../types";
import { Icon } from "../../components/Icon";

function parseDiff(diff: string) {
  let oldLine = 0,
    newLine = 0;
  return diff.split("\n").map((text, index) => {
    const hunk = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(text);
    const kind =
      text.startsWith("+++") ||
      text.startsWith("---") ||
      text.startsWith("@@") ||
      text.startsWith("diff ") ||
      text.startsWith("index ") ||
      text.startsWith("\\ No newline")
        ? "header"
        : text.startsWith("+")
          ? "added"
          : text.startsWith("-")
            ? "removed"
            : "context";
    if (hunk) {
      oldLine = Number(hunk[1]);
      newLine = Number(hunk[2]);
    }
    const oldNumber =
      kind !== "header" && kind !== "added" && oldLine ? oldLine++ : "";
    const newNumber =
      kind !== "header" && kind !== "removed" && newLine ? newLine++ : "";
    return { text, kind, index, oldNumber, newNumber };
  });
}

function PatchDiffViewer({ patch }: { patch: RunResponse["patch"] }) {
  const [changesOnly, setChangesOnly] = useState(false);
  if (!patch)
    return (
      <div className="empty-state">
        <Icon name="code" size={24} />
        <h3>No code changes yet</h3>
        <p>
          The patch will be available after the defender generates a proposal.
        </p>
      </div>
    );
  const lines = parseDiff(patch.diff);
  return (
    <>
      <div className="diff-toolbar">
        <div>
          <Icon name="code" />
          <strong>Patch {String(patch.attempt).padStart(2, "0")}</strong>
          <span className="diff-added">
            +{lines.filter((l) => l.kind === "added").length}
          </span>
          <span className="diff-removed">
            −{lines.filter((l) => l.kind === "removed").length}
          </span>
        </div>
        <label>
          <input
            type="checkbox"
            checked={changesOnly}
            onChange={(e) => setChangesOnly(e.target.checked)}
          />
          Changes only
        </label>
      </div>
      <pre className="diff-code" tabIndex={0} aria-label="Patch code changes">
        <code>
          {lines
            .filter((l) => !changesOnly || l.kind !== "context")
            .map((l) => (
              <span key={l.index} className={`diff-line ${l.kind}`}>
                <span className="line-number" aria-hidden="true">
                  {l.oldNumber}
                </span>
                <span className="line-number" aria-hidden="true">
                  {l.newNumber}
                </span>
                <span>{l.text || " "}</span>
              </span>
            ))}
        </code>
      </pre>
      <p className="fine-print diff-caption">
        Exact unified diff supplied by the backend. Full source files are not
        included.
      </p>
    </>
  );
}
export function EvidenceReport({
  run,
  report,
  reportError,
  fixture,
  events = [],
  view = "results",
}: {
  run: RunResponse | null;
  report: ReportResponse | null;
  reportError: string | null;
  fixture: boolean;
  events?: SecurityEvent[];
  view?: "results" | "diff" | "report";
}) {
  const reduced = useReducedMotion();
  const summary = run?.verification;
  const download = () => {
    if (!report || report.source !== "execution") return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `proofloop-${report.run_id}-report.json`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  if (view === "diff")
    return (
      <section className="technical-view">
        <header className="technical-heading">
          <h1>Code changes</h1>
          <p>
            The exact proposal supplied for this investigation. A patch is not a
            verdict.
          </p>
        </header>
        <div className="code-surface">
          <PatchDiffViewer patch={run?.patch} />
        </div>
      </section>
    );
  if (view === "report")
    return (
      <section className="technical-view">
        <header className="technical-heading">
          <div>
            <h1>Evidence report</h1>
            <p>Saved evidence references, identities and verification scope.</p>
          </div>
          {report && (
            <button className="primary" onClick={download}>
              <Icon name="download" />
              Export evidence report
            </button>
          )}
        </header>
        {report ? (
          <>
            <p className="report-summary">{report.summary}</p>
            <section className="report-limitations">
              <h2>Scope & limitations</h2>
              <ul className="limitations">
                {report.limitations.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
            </section>
            <h2>
              Evidence references{" "}
              <span className="count-badge">
                {report.evidence?.length ?? 0}
              </span>
            </h2>
            {report.evidence?.length ? (
              report.evidence.map((item, index) => (
                <details
                  className="artifact"
                  key={`${item.artifact_id}-${index}`}
                >
                  <summary>{item.description}</summary>
                  <code>{item.artifact_id}</code>
                  <small>SHA-256 {item.sha256}</small>
                </details>
              ))
            ) : (
              <p className="empty-copy">No artifact references supplied.</p>
            )}
          </>
        ) : (
          <div className="empty-state">
            <Icon name="file" size={28} />
            <h2>
              {reportError ? "Report unavailable" : "No saved report yet"}
            </h2>
            <p>
              {fixture
                ? "Fixture previews contain no executed evidence report."
                : (reportError ??
                  "The completed run’s saved report will appear here.")}
            </p>
          </div>
        )}
      </section>
    );
  return (
    <section className="technical-view">
      <header className="technical-heading">
        <h1>Test results</h1>
        <p>
          Recorded counts for the current patch. The independent verifier
          determines the verdict.
        </p>
      </header>
      <div
        className={`verification-context context-${fixture ? "fixture" : (run?.status ?? "pending")}`}
      >
        <Icon name="shield" size={24} />
        <div>
          <strong>
            {fixture
              ? "Illustrative test results"
              : run
                ? labels[run.status]
                : "Awaiting independent execution"}
          </strong>
          <p>
            {fixture
              ? "Illustrative counts. These tests have not been executed."
              : run?.status === "challenging"
                ? "Previous counts cleared. Fresh verification is required."
                : summary
                  ? `Current patch: attempt ${run?.patch?.attempt ?? "—"}`
                  : "Results will appear when the backend records them."}
          </p>
        </div>
      </div>
      <div className="results-heading">
        <span>Test suite</span>
        <span>Passed / total</span>
      </div>
      {(["security", "functional", "adversarial"] as const).map((suite) => {
        const passed = summary?.[`${suite}_passed`],
          total = summary?.[`${suite}_total`];
        return (
          <div
            className={`suite-row ${passed !== undefined && total && passed < total ? "suite-incomplete" : ""}`}
            key={suite}
          >
            <div className="suite-name">
              <Icon
                name={
                  suite === "security"
                    ? "shield"
                    : suite === "functional"
                      ? "code"
                      : "attack"
                }
              />
              <span>
                {suite}
                <small>
                  {suite === "security"
                    ? "Authorization boundaries"
                    : suite === "functional"
                      ? "Legitimate application behavior"
                      : "Additional attack cases"}
                </small>
              </span>
            </div>
            <div className="suite-count">
              <span className="suite-outcome">
                {fixture
                  ? "Preview"
                  : passed === undefined || total === undefined
                    ? "Pending"
                    : !total
                      ? "No checks"
                      : passed < total
                        ? "Not all passing"
                        : "Recorded passing"}
              </span>
              <div className="suite-progress">
                <motion.span
                  initial={false}
                  animate={{
                    width: total ? `${(passed! / total) * 100}%` : "0%",
                  }}
                  transition={{ duration: reduced ? 0 : motionTokens.state }}
                />
              </div>
              <strong>
                {passed ?? "—"}
                <span> / {total ?? "—"}</span>
              </strong>
            </div>
          </div>
        );
      })}
      <p className="evidence-note">
        Individual assertion names are not supplied in this view. Recorded round
        outcomes and saved report references preserve the available evidence.
      </p>
      <RecordedRounds events={events} />
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button className="scope-explanation">
            <Icon name="info" />
            About verification scope
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content className="tooltip-content" sideOffset={6}>
            Only the frozen executed suite is covered. Missing, skipped and
            timed-out checks cannot count as passing.
            <Tooltip.Arrow />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </section>
  );
}
