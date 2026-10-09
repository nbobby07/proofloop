import { ConnectionBadge } from "../../components/ConnectionBadge";
import { useBackendHealth } from "../../hooks/useBackendHealth";
import { API_BASE_URL, getCloudAnalytics } from "../../services/api";
import type { TelemetryAnalyticsResponse } from "../../types";

export function IntegrationStatus({
  health,
}: {
  health: ReturnType<typeof useBackendHealth>;
}) {
  const [cloud, setCloud] = useState<TelemetryAnalyticsResponse | null>(null);
  const [cloudState, setCloudState] = useState("Checking");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getCloudAnalytics(controller.signal)
      .then((result) => {
        if (!active) return;
        setCloud(result);
        setCloudState("SQL verified");
      })
      .catch(() => {
        if (!active) return;
        setCloud(null);
        setCloudState("Unavailable");
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [revision]);
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Integrations</h1>
          <p className="support">
            Service availability and optional evidence tools.
          </p>
        </div>
      </div>
      <section className="panel">
        <div className="integration-row">
          <div>
            <strong>FastAPI backend</strong>
            <code>{API_BASE_URL}</code>
          </div>
          <ConnectionBadge status={health.status} />
          <button
            onClick={health.retry}
            disabled={health.status === "checking"}
          >
            Refresh ↻
          </button>
        </div>
        {health.error && (
          <p className="error-message" role="alert">
            {health.error}
          </p>
        )}
        <div className="integration-row">
          <div>
            <strong>ClickHouse</strong>
            <small>
              {cloud
                ? `${cloud.event_count} real events queried · ${cloud.pending_events} awaiting delivery. Open Analytics for live SQL results.`
                : "Cloud analytics checked independently of backend health. Local evidence stays available."}
            </small>
          </div>
          <span className="badge" role="status">
            {cloudState}
          </span>
          <button
            disabled={cloudState === "Checking"}
            onClick={() => {
              setCloudState("Checking");
              setRevision((v) => v + 1);
            }}
          >
            Refresh ClickHouse
          </button>
        </div>
        {[
          [
            "Guild",
            "Hosted evidence auditor · deployment and execution pending",
          ],
          [
            "ElevenLabs",
            "Evidence-bound briefing routes · availability checked for each completed report",
          ],
          [
            "AkashML + Akash compute",
            "Model requests, cloud deployments, executed checks and lease closure are recorded in Workspace investigations.",
          ],
          [
            "Semgrep / OpenAI",
            "Scanner diagnostics and patch proposals are bound to each investigation's evidence.",
          ],
          [
            "Senso",
            "Live policy retrieval is not configured; reviewed local policies remain authoritative.",
          ],
        ].map(([name, detail]) => (
          <div className="integration-row" key={name}>
            <div>
              <strong>{name}</strong>
              <small>{detail}</small>
            </div>
            <span className="badge">
              {name === "ElevenLabs" ? "See current briefing" : name === "Senso" || name === "Guild" ? "Not verified" : "See run evidence"}
            </span>
          </div>
        ))}
      </section>
    </>
  );
}
import { useEffect, useState } from "react";
