import { useEffect, useState } from "react";
import type { AnalyticsResponse } from "../../types";
import { errorMessage, getAnalytics } from "../../services/api";
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
            <h2>Unsuccessful rounds by challenge family</h2>
          </div>
          <span className="badge">
            {updated
              ? `Fetched ${updated.toLocaleTimeString()}`
              : "Awaiting results"}
          </span>
        </div>
        {patterns.length > 0 && !fixture && (
          <div className="chart-legend">
            <span>Unsuccessful / incomplete rounds</span>
            <span>Rate per challenge family · 0–100%</span>
          </div>
        )}
        {patterns.length > 0 && !fixture && (
          <div
            className="analytics-chart"
            role="img"
            aria-label="Unsuccessful or incomplete rounds by challenge family; exact values are in the table below."
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
                          <strong>{pattern.failures}</strong> unsuccessful /
                          incomplete of {pattern.executions} rounds
                        </p>
                        <p>
                          {pattern.executions
                            ? `${pattern.rate.toFixed(1)}% unsuccessful`
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
                  <th>Unsuccessful / incomplete</th>
                  <th>Verification rounds</th>
                  <th>Unsuccessful rate</th>
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
            Optional ClickHouse delivery is separate from these local results.
            Recorded rounds include timeouts, skipped checks and incomplete
            results. The orchestrator controls selection and budgets; analytics
            never determine security verdicts.
          </p>
        </div>
      </section>
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
          ClickHouse ingestion and adaptive recommendations remain unverified
          until the telemetry service is connected.
        </p>
      </section>
    </>
  );
}
