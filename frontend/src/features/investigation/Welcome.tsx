import { Icon } from "../../components/Icon";
import type { ConnectionStatus } from "../../hooks/useBackendHealth";
export function Welcome({
  start,
  history,
  connection,
  busy,
  opening,
}: {
  start: () => void;
  history: () => void;
  connection: ConnectionStatus;
  busy: boolean;
  opening: boolean;
}) {
  if (opening)
    return (
      <section className="welcome opening-state" aria-busy="true">
        <span className="section-label">Your investigation</span>
        <h1>Opening the saved evidence.</h1>
        <p>Fetching the current result from the backend.</p>
      </section>
    );
  return (
    <section className="welcome">
      <div className="welcome-intro">
        <span className="section-label">Find. Fix. Prove.</span>
        <h1>Find out whether your security fix actually works.</h1>
        <p>
          ProofLoop reproduces security failures, generates fixes, and tests the
          results independently.
        </p>
      </div>
      <div className="target-brief">
        <span className="target-monogram">L</span>
        <div>
          <h2>LedgerLite</h2>
          <p>Synthetic financial application</p>
          <span>Authorization vulnerability demonstration</span>
        </div>
        <span className="target-label">Available target</span>
      </div>
      <div className="welcome-actions">
        <button
          className="primary"
          disabled={busy || connection !== "connected"}
          onClick={start}
          aria-describedby="start-explanation"
        >
          <Icon name="play" />
          {busy ? "Starting investigation…" : "Run security verification"}
        </button>
        <button className="text-button" onClick={history}>
          View previous runs <Icon name="arrow" />
        </button>
      </div>
      <p id="start-explanation" className="action-help">
        {connection === "checking"
          ? "Connecting to the local verification service…"
          : connection === "unavailable"
            ? "The backend is unavailable. Check the connection in Integrations before starting."
            : "Runs the supported LedgerLite demonstration in an isolated environment."}
      </p>
      <ol className="welcome-method">
        <li>
          <span>01</span>
          <h3>Find the problem</h3>
          <p>Reproduce the security failure.</p>
        </li>
        <li>
          <span>02</span>
          <h3>Generate and test a fix</h3>
          <p>Keep failed proposals in the record.</p>
        </li>
        <li>
          <span>03</span>
          <h3>Challenge and verify</h3>
          <p>Let independent checks decide.</p>
        </li>
      </ol>
    </section>
  );
}
