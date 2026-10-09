import type { RunResponse } from "../../types";
import { canChallenge, terminal } from "./lifecycle";
import { Icon } from "../../components/Icon";
import type { EvidenceView } from "../investigation/model";
export function RunControls({
  run,
  busy,
  challenge,
  inspect,
  useLive,
  refresh,
}: {
  run: RunResponse;
  busy: boolean;
  challenge: () => void;
  inspect: (view: EvidenceView) => void;
  useLive: () => void;
  refresh: () => void;
}) {
  if (run.source === "fixture")
    return (
      <div className="outcome-actions">
        <button className="primary" onClick={useLive}>
          Use live backend <Icon name="arrow" />
        </button>
        <p className="action-help">
          Switch to live mode to run the supported demonstration.
        </p>
      </div>
    );
  if (!terminal(run.status))
    return (
      <p className="action-help running-help">
        You can inspect the evidence while this investigation runs.
      </p>
    );
  if (run.status === "verified")
    return (
      <div className="outcome-actions">
        <div className="button-row">
          <button
            className="primary"
            disabled={busy || !canChallenge(run)}
            onClick={challenge}
          >
            <Icon name="refresh" />
            Challenge this fix
          </button>
          <button className="text-button" onClick={() => inspect("diff")}>
            Review code changes <Icon name="arrow" />
          </button>
        </div>
        <p className="action-help">
          {canChallenge(run)
            ? "Runs fresh challenges and replaces this verdict with a new result."
            : "A reproduced baseline and an available patch are required before a fresh challenge."}
        </p>
      </div>
    );
  return (
    <div className="outcome-actions">
      <div className="button-row">
        <button
          className="primary"
          onClick={() =>
            inspect(run.status === "rejected" ? "results" : "audit")
          }
        >
          {run.status === "rejected"
            ? "Inspect failed checks"
            : "Inspect recorded evidence"}
          <Icon name="arrow" />
        </button>
        {canChallenge(run) ? (
          <button onClick={challenge} disabled={busy}>
            Challenge this fix
          </button>
        ) : (
          <button className="text-button" onClick={refresh}>
            Refresh evidence
          </button>
        )}
      </div>
      <p className="action-help">
        {run.status === "rejected"
          ? "Review the recorded outcomes and retained attempts before trying again."
          : "Missing or interrupted checks cannot establish a passing result."}
      </p>
    </div>
  );
}
