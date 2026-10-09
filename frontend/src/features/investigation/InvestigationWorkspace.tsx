import { useRef } from "react";
import type { RefObject } from "react";
import { LayoutGroup, motion, useReducedMotion } from "motion/react";
import { Tabs } from "radix-ui";
import type { ReportResponse, RunResponse, SecurityEvent } from "../../types";
import { Icon } from "../../components/Icon";
import { motionTokens } from "../../components/motion";
import { EvidenceReport } from "../evidence/EvidenceReport";
import { SecurityArena } from "../execution/SecurityArena";
import { EventStream } from "../execution/EventStream";
import { labels, terminal } from "../execution/lifecycle";
import type { EvidenceView } from "./model";
const views: { value: EvidenceView; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "diff", label: "Code changes" },
  { value: "results", label: "Test results" },
  { value: "audit", label: "Audit trail" },
  { value: "report", label: "Report" },
];
export function InvestigationWorkspace({
  run,
  events,
  report,
  reportError,
  busy,
  requestingChallenge,
  challenge,
  refresh,
  useLive,
  newInvestigation,
  view,
  setView,
  presentation,
  enterPresentation,
  presentationTrigger,
}: {
  run: RunResponse;
  events: SecurityEvent[];
  report: ReportResponse | null;
  reportError: string | null;
  busy: boolean;
  requestingChallenge: boolean;
  challenge: () => void;
  refresh: () => void;
  useLive: () => void;
  newInvestigation: () => void;
  view: EvidenceView;
  setView: (view: EvidenceView) => void;
  presentation: boolean;
  enterPresentation: () => void;
  presentationTrigger: RefObject<HTMLButtonElement | null>;
}) {
  const reduced = useReducedMotion();
  const tabTriggers = useRef<
    Partial<Record<EvidenceView, HTMLButtonElement | null>>
  >({});
  const inspect = (next: EvidenceView) => {
    setView(next);
    tabTriggers.current[next]?.focus();
  };
  return (
    <div className="investigation-workspace">
      <div className="investigation-header">
        <div>
          <span className="section-label">Security investigation</span>
          <p>
            {run.target}
            <span> / Authorization</span>
          </p>
        </div>
        {!presentation && (
          <div className="investigation-tools">
            {terminal(run.status) && (
              <button
                className="text-button"
                onClick={newInvestigation}
                disabled={busy}
              >
                New investigation
              </button>
            )}
            <button ref={presentationTrigger} onClick={enterPresentation}>
              <Icon name="external" />
              Presentation mode
            </button>
          </div>
        )}
      </div>
      <LayoutGroup id="investigation-evidence">
        <Tabs.Root
          value={view}
          onValueChange={(value) => setView(value as EvidenceView)}
        >
          <Tabs.List className="evidence-tabs" aria-label="Investigation views">
            {views.map((item) => (
              <Tabs.Trigger
                key={item.value}
                ref={(node) => {
                  tabTriggers.current[item.value] = node;
                }}
                value={item.value}
                className={`tab-${item.value}`}
              >
                {item.label}
                {view === item.value && (
                  <motion.span
                    className="tab-indicator"
                    layoutId={reduced ? undefined : "investigation-tab"}
                    transition={{
                      duration: reduced ? 0 : motionTokens.panel,
                    }}
                  />
                )}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <Tabs.Content
            value="overview"
            forceMount
            hidden={view !== "overview"}
          >
            <SecurityArena
              run={run}
              events={events}
              report={report}
              busy={busy}
              requestingChallenge={requestingChallenge}
              inspect={inspect}
              challenge={challenge}
              useLive={useLive}
              refresh={refresh}
            />
          </Tabs.Content>
          <Tabs.Content value="diff" forceMount hidden={view !== "diff"}>
            <EvidenceReport
              view="diff"
              run={run}
              report={report}
              reportError={reportError}
              fixture={run.source === "fixture"}
              events={events}
            />
          </Tabs.Content>
          <Tabs.Content value="results" forceMount hidden={view !== "results"}>
            <EvidenceReport
              view="results"
              run={run}
              report={report}
              reportError={reportError}
              fixture={run.source === "fixture"}
              events={events}
            />
          </Tabs.Content>
          <Tabs.Content value="audit" forceMount hidden={view !== "audit"}>
            <section className="technical-view">
              <header className="technical-heading">
                <div>
                  <h1>Audit trail</h1>
                  <p>The complete recorded lifecycle, in delivery order.</p>
                </div>
                <button onClick={refresh} disabled={run.source === "fixture"}>
                  <Icon name="refresh" />
                  Refresh evidence
                </button>
              </header>
              <dl className="run-provenance">
                <div>
                  <dt>Run identity</dt>
                  <dd>
                    <code>{run.run_id}</code>
                  </dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>
                    {run.source === "fixture"
                      ? "Fixture · not executed"
                      : "Backend execution"}
                  </dd>
                </div>
                <div>
                  <dt>Exact backend state</dt>
                  <dd>
                    {labels[run.status]} <code>({run.status})</code>
                  </dd>
                </div>
                {run.finding && (
                  <div>
                    <dt>Recorded finding</dt>
                    <dd>
                      {run.finding.title}
                      <code>{run.finding.id}</code>
                    </dd>
                  </div>
                )}
              </dl>
              <EventStream events={events} fixture={run.source === "fixture"} />
            </section>
          </Tabs.Content>
          <Tabs.Content value="report" forceMount hidden={view !== "report"}>
            <EvidenceReport
              view="report"
              run={run}
              report={report}
              reportError={reportError}
              fixture={run.source === "fixture"}
              events={events}
            />
          </Tabs.Content>
        </Tabs.Root>
      </LayoutGroup>
    </div>
  );
}
