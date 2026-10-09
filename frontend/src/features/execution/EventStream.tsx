import { useState } from "react";
import type { SecurityEvent } from "../../types";
import { labels } from "./lifecycle";

export function EventStream({
  events,
  fixture,
}: {
  events: SecurityEvent[];
  fixture: boolean;
}) {
  const [filter, setFilter] = useState("all");
  const visible = events.filter(
    (e) => filter === "all" || e.severity === filter,
  );
  return (
    <section className="panel event-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">
            {fixture ? "Fixture event log" : "Execution event log"}
          </p>
          <h2>Every step, accounted for.</h2>
        </div>
        <label className="filter">
          Severity
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All events</option>
            {["info", "warning", "error", "critical"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
      </div>
      <div
        className="event-scroll"
        tabIndex={0}
        aria-label="Security event log"
      >
        <ol className="event-list">
          {visible.map((e) => (
            <li key={e.event_id} className={`event-${e.severity}`}>
              <time dateTime={e.timestamp}>
                {new Date(e.timestamp).toLocaleTimeString([], {
                  hour12: false,
                })}
              </time>
              <span className="event-dot" />
              <div>
                <strong>{labels[e.stage]}</strong>
                <span className="event-kind">
                  {e.event_type.replaceAll("_", " ")}
                </span>
                <p>{e.message}</p>
              </div>
              <span className="event-source">{e.source}</span>
            </li>
          ))}
        </ol>
        {!visible.length && (
          <p className="empty-copy">
            No matching events. Completed steps are never simulated in live
            mode.
          </p>
        )}
      </div>
      <p className="fine-print">
        {events.length} recorded events · timestamps shown in your local
        timezone · delivery order preserved
      </p>
    </section>
  );
}
