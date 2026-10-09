import { lazy, Suspense, useState } from "react";
import fixtureJson from "../../../contracts/example-run.json";
import { AppShell } from "../components/AppShell";
import type { Page } from "../components/AppShell";
import { useBackendHealth } from "../hooks/useBackendHealth";
import { runPayload } from "../services/validation";
import { useRun } from "../features/execution/useRun";
import { RunControls } from "../features/execution/RunControls";
import { SecurityArena } from "../features/execution/SecurityArena";
import { EventStream } from "../features/execution/EventStream";
import { EvidenceReport } from "../features/evidence/EvidenceReport";
import { IncidentBriefingPlayer } from "../features/briefing/IncidentBriefingPlayer";
import { GuildAuditPanel } from "../features/audit/GuildAuditPanel";
import { SecurityHistory } from "../features/history/SecurityHistory";
import { IntegrationStatus } from "../features/integrations/IntegrationStatus";

const fixtureRun = runPayload(fixtureJson);
const AnalyticsDashboard = lazy(() =>
  import("../features/analytics/AnalyticsDashboard").then((module) => ({
    default: module.AnalyticsDashboard,
  })),
);

export function Dashboard() {
  const [fixture, setFixture] = useState(true);
  const [page, setPage] = useState<Page>("arena");
  const health = useBackendHealth();
  const live = useRun(!fixture);
  const run = fixture ? fixtureRun : live.run;
  const events = fixture ? (fixtureRun.events ?? []) : live.events;
  const openHistoryRun = (id: string) => {
    setFixture(false);
    live.open(id);
    setPage("arena");
  };
  return (
    <AppShell
      page={page}
      navigate={setPage}
      fixture={fixture}
      setFixture={setFixture}
      status={health.status}
    >
      {!fixture && live.error && (
        <div className="notice error" role="alert">
          <span>!</span>
          <div>
            {live.error}
            {run && (
              <small>Last known data is retained; it may be stale.</small>
            )}
          </div>
          <button onClick={live.refresh}>Retry</button>
        </div>
      )}
      {page === "arena" && (
        <>
          <RunControls
            fixture={fixture}
            live={live}
            run={run}
            connection={health.status}
          />
          <SecurityArena run={run} events={events} />
          <div className="evidence-layout">
            <EvidenceReport
              run={run}
              report={fixture ? null : live.report}
              reportError={live.reportError}
              fixture={fixture}
            />
            <EventStream events={events} fixture={fixture} />
          </div>
        </>
      )}
      {page === "analytics" && (
        <Suspense fallback={<p className="empty-copy">Loading analytics…</p>}>
          <AnalyticsDashboard key={String(fixture)} fixture={fixture} />
        </Suspense>
      )}
      {page === "history" && (
        <SecurityHistory history={live.history} open={openHistoryRun} />
      )}
      {page === "integrations" && <IntegrationStatus health={health} />}
      {page === "integrations" && (
        <div className="sponsor-grid">
          <GuildAuditPanel />
          <IncidentBriefingPlayer />
        </div>
      )}
    </AppShell>
  );
}
