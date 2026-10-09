import { useId, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { SecurityEvent } from "../../types";
import { Icon } from "../../components/Icon";
import { motionTokens } from "../../components/motion";
import { labels, recordedOutcome } from "./lifecycle";

function EventMetadata({ event }: { event: SecurityEvent }) {
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  const reduced = useReducedMotion();
  if (!Object.keys(event.metadata ?? {}).length) return null;
  return (
    <div className="event-details">
      <button
        aria-expanded={expanded}
        aria-controls={id}
        onClick={() => setExpanded((value) => !value)}
      >
        {expanded ? "Hide metadata" : "Recorded metadata"}
        <Icon name="chevron" size={11} />
      </button>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            id={id}
            key="metadata"
            initial={{ height: reduced ? "auto" : 0, opacity: reduced ? 1 : 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: reduced ? "auto" : 0, opacity: 0 }}
            transition={{
              duration: reduced ? 0 : motionTokens.panel,
              ease: motionTokens.ease,
            }}
            style={{ overflow: "hidden" }}
          >
            <pre>
              <code>{JSON.stringify(event.metadata, null, 2)}</code>
            </pre>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

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
          <span className="section-index">03</span>
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
              transition={{
                duration: reduced ? 0 : motionTokens.micro,
                ease: motionTokens.ease,
              }}
              className={`event-${e.severity} ${e.event_type === "test_completed" ? `event-outcome-${recordedOutcome(e).tone}` : ""}`}
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
                <EventMetadata event={e} />
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
