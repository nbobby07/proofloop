import { ConnectionBadge } from "../../components/ConnectionBadge";
import { useBackendHealth } from "../../hooks/useBackendHealth";
import { API_BASE_URL } from "../../services/api";

export function IntegrationStatus({
  health,
}: {
  health: ReturnType<typeof useBackendHealth>;
}) {
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
        {[
          [
            "ClickHouse",
            "Persisted-event delivery available · live connection unverified",
          ],
          [
            "Guild",
            "Hosted evidence auditor · deployment and execution pending",
          ],
          [
            "ElevenLabs",
            "Evidence-bound briefing routes · availability checked for each completed report",
          ],
          [
            "Semgrep / Akash / OpenAI / Senso",
            "Availability is not exposed by the current API",
          ],
        ].map(([name, detail]) => (
          <div className="integration-row" key={name}>
            <div>
              <strong>{name}</strong>
              <small>{detail}</small>
            </div>
            <span className="badge">
              {name === "ElevenLabs" ? "See current briefing" : "Not verified"}
            </span>
          </div>
        ))}
      </section>
    </>
  );
}
