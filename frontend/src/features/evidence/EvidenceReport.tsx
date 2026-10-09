import { useState } from "react";
import { Tabs, Tooltip } from "radix-ui";
import type { ReportResponse, RunResponse } from "../../types";
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
}: {
  run: RunResponse | null;
  report: ReportResponse | null;
  reportError: string | null;
  fixture: boolean;
}) {
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
        <div className="heading-with-icon">
          <Icon name="file" />
          <h2>Security evidence</h2>
        </div>
        <span className="subtle-label">
          {fixture ? "Fixture" : "Run evidence"}
        </span>
      </div>
      <Tabs.Root defaultValue="results">
        <Tabs.List className="tabs" aria-label="Evidence views">
          <Tabs.Trigger value="results">Verification</Tabs.Trigger>
          <Tabs.Trigger value="diff">Code changes</Tabs.Trigger>
          <Tabs.Trigger value="report">Evidence report</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="results" className="evidence-content">
          <div className="results-heading">
            <span>Test suite</span>
            <span>Passed / total</span>
          </div>
          {(["security", "functional", "adversarial"] as const).map((suite) => {
            const passed = summary?.[`${suite}_passed`],
              total = summary?.[`${suite}_total`];
            return (
              <div className="suite-row" key={suite}>
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
                  <div className="suite-progress">
                    <span
                      style={{
                        width: total ? `${(passed! / total) * 100}%` : "0%",
                      }}
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
          <div className="evidence-note">
            <Icon name="info" />
            <p>
              {fixture
                ? "Illustrative counts. These tests have not been executed."
                : summary
                  ? "Counts summarize recorded tests. The independent verifier determines the verdict."
                  : "Waiting for independently executed verification results."}
            </p>
          </div>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button className="scope-explanation">
                <Icon name="shield" />
                About verification scope
                <Icon name="info" size={13} />
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
        </Tabs.Content>
        <Tabs.Content value="diff" className="diff-content">
          <PatchDiffViewer patch={run?.patch} />
        </Tabs.Content>
        <Tabs.Content value="report" className="evidence-content">
          {report ? (
            <>
              <div className="report-actions">
                <span className="subtle-label">Saved report</span>
                <button className="small-button" onClick={download}>
                  <Icon name="download" />
                  Download JSON
                </button>
              </div>
              <p className="report-summary">{report.summary}</p>
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
            <div className="empty-state">
              <Icon name="file" size={24} />
              <h3>{reportError ? "Report unavailable" : "No saved report"}</h3>
              <p>
                {fixture
                  ? "Fixture previews contain no executed evidence report."
                  : (reportError ??
                    "The completed run’s saved report will appear here.")}
              </p>
            </div>
          )}
        </Tabs.Content>
      </Tabs.Root>
    </section>
  );
}
