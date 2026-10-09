import { useState } from "react";
import type { ReportResponse, RunResponse } from "../../types";
import { StatusBadge } from "../../components/StatusBadge";

function PatchDiffViewer({ patch }: { patch: RunResponse["patch"] }) {
  const [changesOnly, setChangesOnly] = useState(false);
  if (!patch) return <p className="empty-copy">No patch has been supplied.</p>;
  const lines = patch.diff.split("\n");
  return (
    <>
      <div className="diff-toolbar">
        <span>Unified diff · attempt {patch.attempt}</span>
        <label>
          <input
            type="checkbox"
            checked={changesOnly}
            onChange={(e) => setChangesOnly(e.target.checked)}
          />{" "}
          Changes only
        </label>
      </div>
      <pre className="diff-code" tabIndex={0} aria-label="Patch code changes">
        <code>
          {lines.map((line, i) => {
            const kind =
              line.startsWith("+++") ||
              line.startsWith("---") ||
              line.startsWith("@@")
                ? "header"
                : line.startsWith("+")
                  ? "added"
                  : line.startsWith("-")
                    ? "removed"
                    : "context";
            if (changesOnly && kind === "context") return null;
            return (
              <span key={i} className={`diff-line ${kind}`}>
                <span className="line-number" aria-hidden="true">
                  {i + 1}
                </span>
                {line || " "}
                <br />
              </span>
            );
          })}
        </code>
      </pre>
      <p className="fine-print">
        + Added · − Removed · Full original and patched files are not supplied
        by API v1.
      </p>
    </>
  );
}

export function EvidenceReport({
  run,
  report,
  reportError,
  fixture,
}: {
  run: RunResponse | null;
  report: ReportResponse | null;
  reportError: string | null;
  fixture: boolean;
}) {
  const [tab, setTab] = useState("results");
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
  return (
    <section className="panel evidence-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Security evidence</p>
          <h2>Show the work.</h2>
        </div>
        <StatusBadge status={run?.status} />
      </div>
      <div className="tabs" role="tablist" aria-label="Evidence views">
        {[
          ["results", "Verification"],
          ["diff", "Code changes"],
          ["report", "Evidence report"],
        ].map(([id, name]) => (
          <button
            key={id}
            id={`tab-${id}`}
            role="tab"
            aria-selected={tab === id}
            tabIndex={tab === id ? 0 : -1}
            aria-controls="evidence-content"
            onKeyDown={(event) => {
              const ids = ["results", "diff", "report"];
              const index = ids.indexOf(id);
              const next =
                event.key === "ArrowRight"
                  ? ids[(index + 1) % ids.length]
                  : event.key === "ArrowLeft"
                    ? ids[(index + ids.length - 1) % ids.length]
                    : event.key === "Home"
                      ? ids[0]
                      : event.key === "End"
                        ? ids[ids.length - 1]
                        : null;
              if (next) {
                event.preventDefault();
                setTab(next);
                document.getElementById(`tab-${next}`)?.focus();
              }
            }}
            onClick={() => setTab(id)}
          >
            {name}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="evidence-content" aria-labelledby={`tab-${tab}`}>
        {tab === "results" && (
          <>
            <div className="suite-grid">
              {(["security", "functional", "adversarial"] as const).map(
                (suite) => (
                  <div className="suite" key={suite}>
                    <span>{suite}</span>
                    <strong>
                      {summary ? summary[`${suite}_passed`] : "—"}
                      <small>
                        {" "}
                        / {summary ? summary[`${suite}_total`] : "—"}
                      </small>
                    </strong>
                    <p>
                      {fixture
                        ? "Illustrative counts · not executed"
                        : summary
                          ? "Backend-reported passed / total"
                          : "Awaiting verifier results"}
                    </p>
                  </div>
                ),
              )}
            </div>
            <div className="evidence-note">
              <span>◇</span>
              <p>
                Counts do not establish a verdict. The independent verifier must
                bind required checks to the exact patch. Timeouts, skipped
                checks, and missing evidence cannot count as passing.
              </p>
            </div>
            <p className="fine-print">
              Individual test records and Semgrep scan details require an
              approved contract extension.
            </p>
          </>
        )}
        {tab === "diff" && <PatchDiffViewer patch={run?.patch} />}
        {tab === "report" &&
          (report ? (
            <>
              <p className="report-summary">{report.summary}</p>
              <button className="small-button" onClick={download}>
                Download saved report JSON ↓
              </button>
              <h3>Evidence references</h3>
              {report.evidence?.length ? (
                report.evidence.map((e) => (
                  <div className="artifact" key={e.artifact_id}>
                    <strong>{e.description}</strong>
                    <code>{e.artifact_id}</code>
                    <small>SHA-256 {e.sha256}</small>
                  </div>
                ))
              ) : (
                <p className="empty-copy">No artifact references supplied.</p>
              )}
              <h3>Scope & limitations</h3>
              <ul className="limitations">
                {report.limitations.map((text, i) => (
                  <li key={i}>{text}</li>
                ))}
              </ul>
            </>
          ) : (
            <p className="empty-copy">
              {fixture
                ? "This preview has no executed evidence report."
                : (reportError ??
                  "A completed, saved run report will appear here.")}
            </p>
          ))}
      </div>
    </section>
  );
}
