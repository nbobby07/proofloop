import { useState } from "react";
import type { RunResponse } from "../../types";
import type { ConnectionStatus } from "../../hooks/useBackendHealth";
import type { useRun } from "./useRun";
import { canChallenge, terminal } from "./lifecycle";

export function RunControls({
  fixture,
  live,
  run,
  connection,
}: {
  fixture: boolean;
  live: ReturnType<typeof useRun>;
  run: RunResponse | null;
  connection: ConnectionStatus;
}) {
  const [input, setInput] = useState("");
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow accent">
            Autonomous adversarial security verification
          </p>
          <h1>
            Trust the evidence.
            <br />
            <span>Challenge the patch.</span>
          </h1>
          <p className="support">
            One authorization flaw. An independent verdict. A traceable proof
            loop.
          </p>
        </div>
        <div className="run-actions">
          <button
            className="primary"
            disabled={
              fixture ||
              live.busy ||
              (!!run && !terminal(run.status)) ||
              connection !== "connected"
            }
            onClick={() => void live.start()}
          >
            {live.busy ? "Submitting…" : "Start verification"}
            <span>↗</span>
          </button>
          <button
            disabled={fixture || live.busy || !canChallenge(run)}
            onClick={() => void live.challenge()}
          >
            Challenge again <span>↻</span>
          </button>
          <small>
            {fixture
              ? "Switch to Live backend to execute."
              : "Executes the authorized LedgerLite target."}
          </small>
        </div>
      </div>
      {!fixture && (
        <form
          className="open-run"
          onSubmit={(e) => {
            e.preventDefault();
            live.open(input);
          }}
        >
          <label htmlFor="run-id">Open saved run</label>
          <input
            id="run-id"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Run ID"
            pattern="[A-Za-z0-9_-]{1,128}"
            required
          />
          <button disabled={live.busy}>Open →</button>
          {run && (
            <button type="button" onClick={live.refresh}>
              Refresh ↻
            </button>
          )}
        </form>
      )}
      <div className="run-strip">
        <div>
          <span className="dot" />
          <strong>LedgerLite</strong>
          <span className="muted">/ {run?.run_id ?? "No run selected"}</span>
        </div>
        <span>
          {fixture
            ? "CONTRACT PREVIEW"
            : live.polling
              ? "FETCHING EVENTS"
              : live.updatedAt
                ? `UPDATED ${live.updatedAt.toLocaleTimeString()}`
                : "WAITING FOR EXECUTION"}
        </span>
      </div>
    </>
  );
}
