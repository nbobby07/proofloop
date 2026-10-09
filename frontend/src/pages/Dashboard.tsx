import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import fixtureJson from "../../../contracts/example-run.json";
import { AppShell } from "../components/AppShell";
import type { Page } from "../components/AppShell";
import { useBackendHealth } from "../hooks/useBackendHealth";
import { runPayload } from "../services/validation";
import { useRun } from "../features/execution/useRun";
import { Welcome } from "../features/investigation/Welcome";
import type { EvidenceView } from "../features/investigation/model";
import { BriefingPanel } from "../features/briefing/BriefingPanel";
import { IncidentBriefingPlayer } from "../features/briefing/IncidentBriefingPlayer";
import { GuildAuditPanel } from "../features/audit/GuildAuditPanel";
import { SecurityHistory } from "../features/history/SecurityHistory";
import { IntegrationStatus } from "../features/integrations/IntegrationStatus";
import { readSelection, saveSelection } from "../features/execution/session";
const fixtureRun = runPayload(fixtureJson);
const InvestigationWorkspace = lazy(() =>
  import("../features/investigation/InvestigationWorkspace").then((module) => ({
    default: module.InvestigationWorkspace,
  })),
);
const AnalyticsDashboard = lazy(() =>
  import("../features/analytics/AnalyticsDashboard").then((module) => ({
    default: module.AnalyticsDashboard,
  })),
);

export function Dashboard() {
  const [fixture, updateFixture] = useState(
    () => readSelection("source") === "fixture",
  );
  const [page, setPage] = useState<Page>("arena");
  const [view, setView] = useState<EvidenceView>("overview");
  const [presentation, setPresentation] = useState(false);
  const presentationTrigger = useRef<HTMLButtonElement>(null);
  const priorView = useRef<EvidenceView>("overview");
  const wasPresenting = useRef(false);
  const health = useBackendHealth();
  const live = useRun(!fixture);
  const setFixture = (value: boolean) => {
    saveSelection("source", value ? "fixture" : "execution");
    updateFixture(value);
    setView("overview");
  };
  const exitPresentation = useCallback(() => {
    setPresentation(false);
    setView(priorView.current);
  }, []);
  useEffect(() => {
    if (presentation) document.getElementById("exit-presentation")?.focus();
    else if (wasPresenting.current) presentationTrigger.current?.focus();
    wasPresenting.current = presentation;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") exitPresentation();
    };
    if (presentation) window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [presentation, exitPresentation]);
  const challengeRequested = live.busyAction === "challenge";
  const run = fixture
    ? fixtureRun
    : challengeRequested && live.run
      ? { ...live.run, status: "challenging" as const, verification: null }
      : live.run;
  const report = fixture || challengeRequested ? null : live.report;
  const history = live.history.map((item) =>
    !fixture && run?.run_id === item.run_id ? run : item,
  );
  const events = fixture ? (fixtureRun.events ?? []) : live.events;
  const openHistoryRun = (id: string) => {
    setFixture(false);
    live.open(id);
    setView("overview");
    setPage("arena");
  };
  const newInvestigation = () => {
    live.open("");
    setFixture(false);
    setView("overview");
  };
  return (
    <AppShell
      page={page}
      navigate={setPage}
      fixture={fixture}
      setFixture={setFixture}
      status={health.status}
      presentation={presentation}
      exitPresentation={exitPresentation}
    >
      {!fixture && live.error && (
        <div className="notice error" role="alert">
          <div>
            <strong>We couldn’t complete that request.</strong>
            <p>{live.error}</p>
            {run && (
              <small>
                Last known evidence is retained and may be stale. Refresh before
                relying on it.
              </small>
            )}
          </div>
          <button onClick={live.refresh}>Retry connection</button>
        </div>
      )}
      {page === "arena" &&
        (run ? (
          <Suspense
            fallback={
              <p className="empty-copy" role="status">
                Opening investigation…
              </p>
            }
          >
            <InvestigationWorkspace
              key={run.run_id}
              run={run}
              events={events}
              report={report}
              reportError={live.reportError}
              busy={live.busy}
              requestingChallenge={challengeRequested}
              challenge={() => void live.challenge()}
              refresh={live.refresh}
              useLive={() => setFixture(false)}
              newInvestigation={newInvestigation}
              view={view}
              setView={setView}
              presentation={presentation}
              enterPresentation={() => {
                priorView.current = view;
                setView("overview");
                setPresentation(true);
              }}
              presentationTrigger={presentationTrigger}
            />
          </Suspense>
        ) : (
          <Welcome
            start={() => void live.start()}
            history={() => setPage("history")}
            connection={health.status}
            busy={live.busy}
            opening={!!live.selectedRunId && !live.error}
          />
        ))}
      {page === "history" && (
        <SecurityHistory history={history} open={openHistoryRun} />
      )}
      {page === "analytics" && (
        <Suspense fallback={<p className="empty-copy">Loading analytics…</p>}>
          <AnalyticsDashboard key={String(fixture)} fixture={fixture} />
        </Suspense>
      )}
      {page === "integrations" && (
        <>
          <IntegrationStatus health={health} />
          <div className="sponsor-grid">
            <GuildAuditPanel />
            {report ? (
              <BriefingPanel key={JSON.stringify(report)} report={report} />
            ) : (
              <IncidentBriefingPlayer />
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}
