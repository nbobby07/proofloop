import type { RunResponse } from "../../types";
import { StatusBadge } from "../../components/StatusBadge";

export function SecurityHistory({
  history,
  open,
}: {
  history: RunResponse[];
  open: (id: string) => void;
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Run history</h1>
          <p className="support">
            Verification runs opened in this browser session.
          </p>
        </div>
      </div>
      <section className="panel">
        {history.length ? (
          history.map((item) => (
            <button
              className="history-row"
              key={item.run_id}
              onClick={() => open(item.run_id)}
            >
              <span>
                <strong>{item.run_id}</strong>
                <small>{item.target} · execution</small>
              </span>
              <StatusBadge status={item.status} />
              <span>Open ↗</span>
            </button>
          ))
        ) : (
          <p className="empty-copy">
            No live runs observed. Fixture previews are excluded from history.
          </p>
        )}
      </section>
    </>
  );
}
