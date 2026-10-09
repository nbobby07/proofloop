import { useState } from "react";
import { Dialog } from "radix-ui";
import { X } from "lucide-react";
import type { RunResponse } from "../../types";
import type { ConnectionStatus } from "../../hooks/useBackendHealth";
import type { useRun } from "./useRun";
import { canChallenge, terminal } from "./lifecycle";
import { Icon } from "../../components/Icon";

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
  const [showOpen, setShowOpen] = useState(false);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow page-kicker">
            SECURITY OPERATIONS <span>/</span> VERIFICATION
          </p>
          <h1>
            Security verification
            <span className="heading-period" aria-hidden="true">
              .
            </span>
          </h1>
          <p className="support">
            Reproduce the vulnerability. Review the patch. Inspect the evidence.
          </p>
        </div>
        <div className="run-actions">
          {!fixture && (
            <Dialog.Root open={showOpen} onOpenChange={setShowOpen}>
              <Dialog.Trigger asChild>
                <button>
                  <Icon name="history" />
                  Open run
                </button>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="dialog-overlay" />
                <Dialog.Content className="dialog-content">
                  <Dialog.Title>Open saved run</Dialog.Title>
                  <Dialog.Description>
                    Enter the run ID from a previous verification.
                  </Dialog.Description>
                  <form
                    className="open-run"
                    onSubmit={(e) => {
                      e.preventDefault();
                      live.open(input);
                      setShowOpen(false);
                    }}
                  >
                    <label htmlFor="run-id">Run ID</label>
                    <input
                      id="run-id"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder="run_…"
                      pattern="[A-Za-z0-9_-]{1,128}"
                      required
                    />
                    <button className="primary" disabled={live.busy}>
                      Open run
                      <Icon name="arrow" />
                    </button>
                  </form>
                  <Dialog.Close className="dialog-close" aria-label="Close">
                    <X size={16} />
                  </Dialog.Close>
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
          )}
          <button
            className="challenge-action"
            title="Invalidate the previous verdict and execute fresh independent challenges"
            disabled={fixture || live.busy || !canChallenge(run)}
            onClick={() => void live.challenge()}
          >
            <Icon name="refresh" />
            {live.busyAction === "challenge"
              ? "Requesting challenge…"
              : "Challenge again"}
          </button>
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
            <Icon name="play" />
            {live.busyAction === "start" ? "Submitting…" : "Start verification"}
          </button>
        </div>
      </div>
      {!fixture && run?.status === "challenging" && (
        <div className="challenge-notice" role="status">
          <Icon name="refresh" />
          <div>
            <strong>
              {live.busyAction === "challenge"
                ? "Requesting fresh challenges"
                : "Fresh challenges in progress"}
            </strong>
            <p>
              {live.busyAction === "challenge"
                ? "Previous result withheld while the backend accepts the request."
                : "Previous verdict invalidated. New events and independent verification must complete before a new result is recorded."}
            </p>
          </div>
          <span className="badge">Awaiting verdict</span>
        </div>
      )}
      <div className="run-strip">
        <div>
          <span className="eyebrow">CURRENT RUN</span>
          <code>{run?.run_id ?? "No run selected"}</code>
          {fixture && <span className="fixture-inline">Fixture</span>}
        </div>
        <div className="run-freshness">
          <span className={live.polling && !fixture ? "dot fetching" : "dot"} />
          <span>
            {fixture
              ? "Read-only preview"
              : live.polling
                ? "Fetching events"
                : live.updatedAt
                  ? `Updated ${live.updatedAt.toLocaleTimeString()}`
                  : "Awaiting execution"}
          </span>
          {!fixture && run && (
            <button
              className="plain-icon"
              title="Refresh run"
              aria-label="Refresh run"
              onClick={live.refresh}
            >
              <Icon name="refresh" />
            </button>
          )}
        </div>
      </div>
    </>
  );
}
