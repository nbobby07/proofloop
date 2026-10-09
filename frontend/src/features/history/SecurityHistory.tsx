import { useState } from "react";
import type { RunResponse } from "../../types";
import { StatusBadge } from "../../components/StatusBadge";
import { Icon } from "../../components/Icon";
export function SecurityHistory({
  history,
  open,
}: {
  history: RunResponse[];
  open: (id: string) => void;
}) {
  const [input, setInput] = useState("");
  return (
    <>
      <header className="page-heading">
        <h1>Investigation history</h1>
        <p>
          Live runs opened in this browser session. Statuses are last observed;
          open an investigation to fetch its current evidence.
        </p>
      </header>
      <form
        className="history-open"
        onSubmit={(event) => {
          event.preventDefault();
          open(input.trim());
        }}
      >
        <label htmlFor="saved-run">Open a saved investigation</label>
        <div>
          <input
            id="saved-run"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Run ID, such as run_…"
            pattern="[A-Za-z0-9_-]{1,128}"
            required
          />
          <button className="primary">
            Open saved run <Icon name="arrow" />
          </button>
        </div>
      </form>
      <section
        className="history-list"
        aria-label="Investigations opened this session"
      >
        {history.length ? (
          history.map((item) => (
            <button
              className="history-row"
              key={item.run_id}
              onClick={() => open(item.run_id)}
            >
              <span>
                <strong>{item.target}</strong>
                <small>
                  <code>{item.run_id}</code>
                </small>
              </span>
              <StatusBadge status={item.status} />
              <Icon name="arrow" />
            </button>
          ))
        ) : (
          <div className="empty-state">
            <Icon name="history" size={28} />
            <h2>No investigations opened yet</h2>
            <p>
              Your observed live runs will appear here. Fixture previews are
              excluded.
            </p>
          </div>
        )}
      </section>
    </>
  );
}
