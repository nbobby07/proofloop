import type { SecurityEvent } from "../../types";
import { Icon } from "../../components/Icon";

import { recordedOutcome } from "./lifecycle";

export function RecordedRounds({ events }: { events: SecurityEvent[] }) {
  const rounds = events.filter(
    (event) => event.event_type === "test_completed",
  );
  if (!rounds.length) return null;
  return (
    <details className="recorded-rounds">
      <summary>
        <Icon name="history" />
        <span>Recorded verification rounds</span>
        <span className="count-badge">{rounds.length}</span>
      </summary>
      <p className="fine-print">
        Historical outcomes remain here after retries and fresh challenges. The
        current verdict appears above.
      </p>
      <ol>
        {rounds.map((event) => {
          const outcome = recordedOutcome(event);
          const attempt =
            typeof event.metadata?.attempt === "number"
              ? event.metadata?.attempt
              : null;
          return (
            <li key={event.event_id} className={`round-${outcome.tone}`}>
              <div className="round-label">
                <strong>
                  {attempt
                    ? `Attempt ${String(attempt).padStart(2, "0")}`
                    : "Recorded round"}
                </strong>
                <span>
                  {event.stage === "challenging" ? "Challenge" : "Verification"}
                </span>
              </div>
              <span className={`round-outcome outcome-${outcome.tone}`}>
                {outcome.label}
              </span>
              <p>{event.message}</p>
              <code>
                {typeof event.metadata?.test_execution_id === "string"
                  ? event.metadata?.test_execution_id
                  : event.event_id}
              </code>
            </li>
          );
        })}
      </ol>
    </details>
  );
}
