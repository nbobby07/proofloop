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
          <p className="eyebrow">Security history</p>
          <h1>Keep the evidence.</h1>
          <p className="support">
            Live runs observed in this browser session. Persistent listing
            requires an API extension.
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
