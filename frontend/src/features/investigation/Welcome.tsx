import { Icon } from "../../components/Icon";
import { useState } from "react";
import type { ConnectionStatus } from "../../hooks/useBackendHealth";
export function Welcome({
  start,
  history,
  connection,
  busy,
  opening,
}: {
  start: (
    target: "LedgerLite" | "LedgerLite Workspace",
    mode: "local" | "local_akash",
  ) => void;
  history: () => void;
  connection: ConnectionStatus;
  busy: boolean;
  opening: boolean;
}) {
  const [target, setTarget] = useState<"LedgerLite" | "LedgerLite Workspace">(
    "LedgerLite",
  );
  const [mode, setMode] = useState<"local" | "local_akash">("local");
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
          <h2>{target === "LedgerLite" ? "LedgerLite Classic" : target}</h2>
          <p>Synthetic financial application</p>
          <span>
            {target === "LedgerLite"
              ? "Authorization vulnerability demonstration"
              : "Organizations, roles, invoices, search, and batch exports"}
          </span>
        </div>
        <span className="target-label">Available target</span>
      </div>
      <div className="workspace-options">
        <label>
          Application
          <select
            value={target}
            onChange={(e) => {
              setTarget(e.target.value as typeof target);
              setMode("local");
            }}
            disabled={busy}
          >
            <option value="LedgerLite">
              LedgerLite Classic · known vulnerability
            </option>
            <option value="LedgerLite Workspace">
              LedgerLite Workspace · fresh audit
            </option>
          </select>
        </label>
        {target === "LedgerLite Workspace" && (
          <>
            <label>
              Verification location
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as typeof mode)}
                disabled={busy}
              >
                <option value="local">Local · AkashML challenges</option>
                <option value="local_akash">
                  Local + Akash compute · compare executions
                </option>
              </select>
            </label>
            <a href="http://127.0.0.1:8010" target="_blank" rel="noreferrer">
              Open LedgerLite Workspace ↗
            </a>
          </>
        )}
      </div>
      <div className="welcome-actions">
        <button
          className="primary"
          disabled={busy || connection !== "connected"}
          onClick={() => start(target, mode)}
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
            : target === "LedgerLite"
              ? "Runs the supported LedgerLite demonstration in an isolated environment."
              : "Audits the preserved AI-generated application. A clean audit does not invent a vulnerability or patch."}
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
