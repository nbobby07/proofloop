import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { SecurityEvent } from "../../types";
import { Icon } from "../../components/Icon";
import { labels } from "./lifecycle";

export function EventStream({
  events,
  fixture,
}: {
  events: SecurityEvent[];
  fixture: boolean;
}) {
  const [filter, setFilter] = useState("all");
  const reduced = useReducedMotion();
  const visible = events.filter(
    (e) => filter === "all" || e.severity === filter,
  );
  return (
    <section className="panel event-panel">
      <div className="section-heading">
        <div className="heading-with-icon">
          <Icon name="terminal" />
          <h2>Event stream</h2>
          <span className="count-badge">{events.length}</span>
        </div>
        <label className="filter">
          <span className="sr-only">Severity</span>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All severities</option>
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
            <motion.li
              key={e.event_id}
              initial={reduced ? false : { opacity: 0, y: 3 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.15 }}
              className={`event-${e.severity}`}
            >
              <span className="event-dot" />
              <div className="event-content">
                <div className="event-meta">
                  <strong>{labels[e.stage]}</strong>
                  <time dateTime={e.timestamp}>
                    {new Date(e.timestamp).toLocaleTimeString([], {
                      hour12: false,
                    })}
                  </time>
                </div>
                <p>{e.message}</p>
                <span className="event-kind">
                  {e.event_type.replaceAll("_", " ")}
                </span>
                <span className="event-source">{e.source}</span>
              </div>
            </motion.li>
          ))}
        </ol>
        {!visible.length && (
          <div className="empty-state">
            <Icon name="terminal" size={24} />
            <h3>No events to display</h3>
            <p>
              {filter !== "all"
                ? "No recorded events match this severity."
                : "Run events will appear as the backend records them."}
            </p>
          </div>
        )}
      </div>
      <div className="event-footer">
        <span className="dot" />
        <span>
          {fixture ? "Fixture events · not executed" : "Execution events"} ·
          local time
        </span>
      </div>
    </section>
  );
}
