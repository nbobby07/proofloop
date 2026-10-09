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
import { BriefingPanel } from "../features/briefing/BriefingPanel";
import { IncidentBriefingPlayer } from "../features/briefing/IncidentBriefingPlayer";
import { GuildAuditPanel } from "../features/audit/GuildAuditPanel";
import { SecurityHistory } from "../features/history/SecurityHistory";
import { IntegrationStatus } from "../features/integrations/IntegrationStatus";

import { readSelection, saveSelection } from "../features/execution/session";

const fixtureRun = runPayload(fixtureJson);
const AnalyticsDashboard = lazy(() =>
  import("../features/analytics/AnalyticsDashboard").then((module) => ({
    default: module.AnalyticsDashboard,
  })),
);

export function Dashboard() {
  const [fixture, updateFixture] = useState(
    () => readSelection("source") !== "execution",
  );
  const setFixture = (value: boolean) => {
    saveSelection("source", value ? "fixture" : "execution");
    updateFixture(value);
  };
  const [page, setPage] = useState<Page>("arena");
  const health = useBackendHealth();
  const live = useRun(!fixture);
  // Suppress old evidence while the challenge request is in flight, even before
  // its acceptance arrives. A rejected request restores the last known snapshot.
  const challengeRequested = live.busyAction === "challenge";
  const run = fixture
    ? fixtureRun
    : challengeRequested && live.run
      ? { ...live.run, status: "challenging" as const, verification: null }
      : live.run;
  const report = fixture || challengeRequested ? null : live.report;
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
          <SecurityArena run={run} events={events} report={report} />
          <div className="evidence-layout">
            <EvidenceReport
              run={run}
              events={events}
              report={report}
              reportError={live.reportError}
              fixture={fixture}
            />
            <div className="review-rail">
              <EventStream events={events} fixture={fixture} />
              {report && (
                <BriefingPanel key={JSON.stringify(report)} report={report} />
              )}
            </div>
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
          {report ? (
            <BriefingPanel key={JSON.stringify(report)} report={report} />
          ) : (
            <IncidentBriefingPlayer />
          )}
        </div>
      )}
    </AppShell>
  );
}
