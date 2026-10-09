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
          <p className="eyebrow">Integration readiness</p>
          <h1>
            Connected claims
            <br />
            <span>need receipts.</span>
          </h1>
          <p className="support">
            Availability is shown only where the current contract provides
            evidence.
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
            "Telemetry adapter · route wiring and real execution pending",
          ],
          [
            "Guild",
            "Hosted evidence auditor · deployment and execution pending",
          ],
          [
            "ElevenLabs",
            "Narration adapter · credentials and audio route pending",
          ],
          [
            "Semgrep / Akash / OpenAI / Senso",
            "Developer A owns these integrations; status is not exposed by API v1",
          ],
        ].map(([name, detail]) => (
          <div className="integration-row" key={name}>
            <div>
              <strong>{name}</strong>
              <small>{detail}</small>
            </div>
            <span className="badge">Not verified</span>
          </div>
        ))}
      </section>
    </>
  );
}
