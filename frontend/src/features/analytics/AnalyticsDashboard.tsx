import { useEffect, useState } from "react";
import type {
  AnalyticsResponse,
  TelemetryAnalyticsResponse,
} from "../../types";
import {
  errorMessage,
  getAnalytics,
  getCloudAnalytics,
} from "../../services/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { Icon } from "../../components/Icon";

export function AnalyticsDashboard({ fixture }: { fixture: boolean }) {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [cloud, setCloud] = useState<TelemetryAnalyticsResponse | null>(null);
  const [localFallback, setLocalFallback] = useState(false);
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
        let response: AnalyticsResponse;
        try {
          const result = await getCloudAnalytics(controller.signal);
          if (!active) return;
          setCloud(result);
          setLocalFallback(false);
          response = result.analytics;
        } catch {
          if (!active) return;
          setCloud(null);
          setData(null);
          setUpdated(null);
          setLocalFallback(true);
          response = await getAnalytics(controller.signal);
        }
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
  const patterns = [...(data?.failure_patterns ?? [])]
    .map((pattern) => ({
      ...pattern,
      rate: pattern.executions
        ? (pattern.failures / pattern.executions) * 100
        : 0,
    }))
    .sort(
      (a, b) =>
        b.failures / Math.max(1, b.executions) -
        a.failures / Math.max(1, a.executions),
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Security analytics</h1>
          <p className="support">
            Persisted execution outcomes, including unsuccessful and incomplete
            verification rounds.
          </p>
        </div>
        <button
          disabled={fixture || loading}
          onClick={() => setAttempt((v) => v + 1)}
        >
          <Icon name="refresh" />
          Refresh analytics
        </button>
      </div>
      {!fixture && cloud && (
        <section
          className="panel analytics-panel"
          aria-label="ClickHouse query evidence"
        >
          <div className="section-heading">
            <h2>Live from ClickHouse</h2>
            <span className="badge">SQL-backed execution history</span>
          </div>
          <p>
            {cloud.event_count} deduplicated events · {cloud.pending_events}{" "}
            local events awaiting delivery · {cloud.query_ms.toFixed(0)} ms to
            fetch this SQL snapshot
          </p>
          <p className="fine-print">
            Latest recorded event:{" "}
            {cloud.latest_event_at
              ? new Date(cloud.latest_event_at).toLocaleString()
              : "No events yet"}
            . Query time includes network latency; this is a small real dataset,
            not a scale benchmark.
          </p>
        </section>
      )}
      {!fixture && localFallback && (
        <div className="notice" role="status">
          ClickHouse is unavailable or disabled.{" "}
          {data
            ? "Showing locally persisted analytics; these values are not a live SQL result."
            : "Local analytics are loading or unavailable; no cloud result is shown."}
        </div>
      )}
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
                  ? "Recorded backend outcomes"
                  : loading
                    ? "Loading…"
                    : "No data available"}
            </small>
          </div>
        ))}
      </div>
      <section className="panel analytics-panel">
        <div className="section-heading">
          <div>
            <h2>
              {cloud
                ? "Failed rounds by challenge family"
                : "Unsuccessful rounds by challenge family"}
            </h2>
          </div>
          <span className="badge">
            {updated
              ? `Fetched ${updated.toLocaleTimeString()}`
              : "Awaiting results"}
          </span>
        </div>
        {patterns.length > 0 && !fixture && (
          <div className="chart-legend">
            <span>
              {cloud
                ? "Explicit failures / recorded rounds"
                : "Unsuccessful / incomplete rounds"}
            </span>
            <span>Rate per challenge family · 0–100%</span>
          </div>
        )}
        {patterns.length > 0 && !fixture && (
          <div
            className="analytics-chart"
            role="img"
            aria-label="Recorded round outcomes by challenge family; exact values are in the table below."
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={patterns}
                layout="vertical"
                margin={{ top: 10, right: 25, bottom: 5, left: 0 }}
              >
                <CartesianGrid horizontal={false} stroke="#d6ddd4" />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  ticks={[0, 25, 50, 75, 100]}
                  tickFormatter={(value: number) => `${value}%`}
                  tick={{ fill: "#57666e", fontSize: 13 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="challenge_family"
                  width={130}
                  tick={{ fill: "#57666e", fontSize: 13 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: "#25303805" }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const pattern = payload[0]
                      .payload as (typeof patterns)[number];
                    return (
                      <div className="chart-tooltip">
                        <b>{pattern.challenge_family}</b>
                        <p>
                          <strong>{pattern.failures}</strong>{" "}
                          {cloud ? "failed" : "unsuccessful / incomplete"} of{" "}
                          {pattern.executions} rounds
                        </p>
                        <p>
                          {pattern.executions
                            ? `${pattern.rate.toFixed(1)}% ${cloud ? "failed" : "unsuccessful"}`
                            : "Rate unavailable · no rounds"}
                        </p>
                      </div>
                    );
                  }}
                />
                <Bar
                  dataKey="rate"
                  name="Unsuccessful rate"
                  fill="#aa695c"
                  radius={[0, 3, 3, 0]}
                  maxBarSize={22}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {patterns.length > 0 && !fixture ? (
          <div
            className="pattern-table"
            tabIndex={0}
            aria-label="Exact analytics values"
          >
            <table>
              <thead>
                <tr>
                  <th>Challenge family</th>
                  <th>
                    {cloud ? "Explicit failures" : "Unsuccessful / incomplete"}
                  </th>
                  <th>Verification rounds</th>
                  <th>{cloud ? "Failure rate" : "Unsuccessful rate"}</th>
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
          <Icon name="info" />
          <p>
            {cloud
              ? `ClickHouse counts explicit failures in the numerator and nonconflicting recorded outcomes in the denominator. ${cloud.incomplete_rounds} rounds have incomplete or unknown outcomes. `
              : "Local analytics include unsuccessful and incomplete outcomes. "}
            These are verification rounds, not individual checks. The
            orchestrator controls selection and budgets; analytics never
            determine security verdicts.
          </p>
        </div>
      </section>
      {cloud ? (
        <section className="panel analytics-panel">
          <h2>What the execution history tells us</h2>
          <p>
            {patterns[0]
              ? `${patterns[0].failures} of ${patterns[0].executions} recorded ${patterns[0].challenge_family.replaceAll("_", " ")} rounds failed. Review unsuccessful attempts before accepting another proposed fix.`
              : "No completed verification rounds are recorded yet."}
          </p>
          <p>
            Average proposals per observed run:{" "}
            <strong>
              {cloud.mean_patch_attempts?.toFixed(2) ?? "Unavailable"}
            </strong>
            . Average verification stage:{" "}
            <strong>
              {cloud.mean_verification_duration_ms == null
                ? "Unavailable"
                : `${(cloud.mean_verification_duration_ms / 1000).toFixed(2)} seconds`}
            </strong>
            .
          </p>
          <p className="fine-print">
            Descriptive history helps decide what to inspect. It does not
            generate attacks, alter the frozen test suite, or establish a
            security verdict.
          </p>
        </section>
      ) : (
        <section className="panel planned-metrics">
          <h2>Additional telemetry</h2>
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
            These measurements are not available in the current analytics feed.
            Connect ClickHouse to view delivery coverage and available SQL
            metrics.
          </p>
        </section>
      )}
    </>
  );
}
