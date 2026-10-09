import { useEffect, useState } from "react";
import type { AnalyticsResponse } from "../../types";
import { errorMessage, getAnalytics } from "../../services/api";

export function AnalyticsDashboard({ fixture }: { fixture: boolean }) {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [updated, setUpdated] = useState<Date | null>(null);
  useEffect(() => {
    if (fixture) return;
    const controller = new AbortController();
    let active = true,
      timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      setLoading(true);
      try {
        const response = await getAnalytics(controller.signal);
        if (!active) return;
        if (response.source !== "execution")
          throw new Error("Live analytics rejected fixture data.");
        setData(response);
        setError(null);
        setUpdated(new Date());
        timer = setTimeout(load, 8000);
      } catch (reason) {
        if (active) setError(errorMessage(reason));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [fixture, attempt]);
  const patterns = [...(data?.failure_patterns ?? [])].sort(
    (a, b) =>
      b.failures / Math.max(1, b.executions) -
      a.failures / Math.max(1, a.executions),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">ClickHouse · security observability</p>
          <h1>
            History informs
            <br />
            <span>the next challenge.</span>
          </h1>
          <p className="support">
            SQL-derived outcomes. Traceable recommendations. No synthetic
            totals.
          </p>
        </div>
        <button
          disabled={fixture || loading}
          onClick={() => setAttempt((v) => v + 1)}
        >
          Refresh analytics ↻
        </button>
      </div>
      {fixture && (
        <div className="notice">
          Fixture preview does not feed production analytics. Switch to Live
          backend to query real data.
        </div>
      )}
      {!fixture && error && (
        <div className="notice error" role="alert">
          {error}
          {data && " Previously fetched results below are stale."}
        </div>
      )}
      <div className="metric-grid">
        {[
          ["Runs observed", data?.run_count],
          ["Verified", data?.verified_count],
          ["Rejected", data?.rejected_count],
          [
            "Other / in progress",
            data
              ? data.run_count - data.verified_count - data.rejected_count
              : undefined,
          ],
        ].map(([label, value]) => (
          <div className="panel metric" key={label}>
            <span className="eyebrow">{label}</span>
            <strong>{fixture ? "—" : (value ?? "—")}</strong>
            <small>
              {fixture
                ? "Live data only"
                : data
                  ? "API v1 · SQL-backed adapter required"
                  : loading
                    ? "Loading…"
                    : "No data available"}
            </small>
          </div>
        ))}
      </div>
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Adaptive testing</p>
            <h2>Where checks fail.</h2>
          </div>
          <span className="badge">
            {updated
              ? `Fetched ${updated.toLocaleTimeString()}`
              : "Awaiting SQL results"}
          </span>
        </div>
        {patterns.length && !fixture ? (
          <div className="pattern-table">
            <table>
              <thead>
                <tr>
                  <th>Challenge family</th>
                  <th>Failures</th>
                  <th>Recorded outcomes</th>
                  <th>Observed failure rate</th>
                </tr>
              </thead>
              <tbody>
                {patterns.map((p) => (
                  <tr key={p.challenge_family}>
                    <td>{p.challenge_family}</td>
                    <td>{p.failures}</td>
                    <td>{p.executions}</td>
                    <td>
                      <div className="rate-cell">
                        <span className="rate-track">
                          <span
                            style={{
                              width: `${p.executions ? (p.failures / p.executions) * 100 : 0}%`,
                            }}
                          />
                        </span>
                        {p.executions
                          ? `${((p.failures / p.executions) * 100).toFixed(1)}%`
                          : "N/A"}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty-copy">
            No production failure patterns available. A small sample cannot
            establish a trend.
          </p>
        )}
        <div className="evidence-note">
          <span>↗</span>
          <p>
            ClickHouse recommendations can prioritize allowlisted challenges.
            Recorded outcomes include timeouts, skipped checks and incomplete
            results. The orchestrator controls selection and budgets;
            analytics never determine security verdicts.
          </p>
        </div>
      </section>
      <section className="panel planned-metrics">
        <p className="eyebrow">Awaiting coordinated API fields</p>
        <h2>More detail, when evidence supports it.</h2>
        <div>
          {[
            "Executed test totals",
            "Attack reproduction rate",
            "Average patch attempts",
            "Verification duration",
            "Outcomes over time",
            "Regression trends",
          ].map((label) => (
            <span className="badge" key={label}>
              {label} · PLANNED
            </span>
          ))}
        </div>
        <p className="fine-print">
          The frozen analytics response does not expose these metrics. The
          telemetry adapter can compute extended SQL results for A to expose
          through an approved contract.
        </p>
      </section>
    </>
  );
}
