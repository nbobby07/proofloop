import type { ReactNode } from "react";
import { LayoutGroup, motion, useReducedMotion } from "motion/react";
import { Popover, Tooltip } from "radix-ui";
import { motionTokens } from "./motion";
import type { ConnectionStatus } from "../hooks/useBackendHealth";
import { ConnectionBadge } from "./ConnectionBadge";
import { Icon, ProofLoopMark } from "./Icon";
import type { IconName } from "./Icon";

export type Page = "arena" | "analytics" | "history" | "integrations";
const pages: { id: Page; label: string; icon: IconName }[] = [
  { id: "arena", label: "Verification", icon: "arena" },
  { id: "history", label: "History", icon: "history" },
  { id: "analytics", label: "Analytics", icon: "analytics" },
  { id: "integrations", label: "Integrations", icon: "integrations" },
];
export function AppShell({
  page,
  navigate,
  fixture,
  setFixture,
  status,
  presentation = false,
  exitPresentation,
  children,
}: {
  page: Page;
  navigate: (page: Page) => void;
  fixture: boolean;
  setFixture: (fixture: boolean) => void;
  status: ConnectionStatus;
  presentation?: boolean;
  exitPresentation?: () => void;
  children: ReactNode;
}) {
  const reduced = useReducedMotion();
  return (
    <Tooltip.Provider delayDuration={300}>
      <div className={`app-shell ${presentation ? "presentation-mode" : ""}`}>
        <a className="skip-link" href="#main-content">
          Skip to workspace
        </a>
        {!presentation && (
          <aside className="sidebar">
            <a
              className="brand"
              href="#verification"
              onClick={() => navigate("arena")}
            >
              <ProofLoopMark />
              <span>ProofLoop</span>
            </a>
            <p className="brand-caption">Independent security verification.</p>
            <LayoutGroup id="workspace-nav">
              <nav aria-label="Main navigation">
                {pages.map((item) => (
                  <button
                    key={item.id}
                    className={`nav-item ${page === item.id ? "nav-active" : ""}`}
                    aria-current={page === item.id ? "page" : undefined}
                    onClick={() => navigate(item.id)}
                  >
                    {page === item.id && (
                      <motion.span
                        className="nav-selection"
                        layoutId={reduced ? undefined : "active-page"}
                        transition={{
                          duration: reduced ? 0 : motionTokens.panel,
                        }}
                      />
                    )}
                    <Icon name={item.icon} />
                    <span>{item.label}</span>
                  </button>
                ))}
              </nav>
            </LayoutGroup>
            <div className="sidebar-footer">
              <ConnectionBadge status={status} />
              <p>Local verification workspace</p>
            </div>
          </aside>
        )}
        <main id="main-content" tabIndex={-1}>
          <header className="topbar">
            {presentation ? (
              <>
                <span className="presentation-brand">
                  <ProofLoopMark />
                  ProofLoop <span>Presentation</span>
                </span>
                <button id="exit-presentation" onClick={exitPresentation}>
                  Exit presentation <kbd>Esc</kbd>
                </button>
              </>
            ) : (
              <>
                <span className="page-location">
                  {pages.find((item) => item.id === page)?.label}
                </span>
                <Popover.Root>
                  <Popover.Trigger asChild>
                    <button
                      className={`source-trigger ${fixture ? "source-fixture" : ""}`}
                    >
                      <span className="dot" />
                      {fixture ? "Fixture preview" : "Live backend"}
                      <Icon name="chevron" size={14} />
                      <span className="sr-only"> — change data source</span>
                    </button>
                  </Popover.Trigger>
                  <Popover.Portal>
                    <Popover.Content
                      className="source-popover"
                      align="end"
                      sideOffset={10}
                    >
                      <h2>Data source</h2>
                      <p>Choose real execution or an illustrative preview.</p>
                      <div
                        className="source-options"
                        role="group"
                        aria-label="Data source"
                      >
                        <Popover.Close asChild>
                          <button
                            aria-pressed={!fixture}
                            onClick={() => setFixture(false)}
                          >
                            <strong>Live backend</strong>
                            <span>
                              Run the supported LedgerLite investigation.
                            </span>
                          </button>
                        </Popover.Close>
                        <Popover.Close asChild>
                          <button
                            aria-pressed={fixture}
                            onClick={() => setFixture(true)}
                          >
                            <strong>Fixture preview</strong>
                            <span>
                              Explore illustrative results. No execution.
                            </span>
                          </button>
                        </Popover.Close>
                      </div>
                    </Popover.Content>
                  </Popover.Portal>
                </Popover.Root>
              </>
            )}
          </header>
          <div className="content">
            {fixture && (
              <div className="fixture-banner">
                <Icon name="info" />
                <div>
                  <strong>Fixture preview</strong>
                  <span>
                    Illustrative contract data. No attacks or tests have been
                    executed.
                  </span>
                </div>
              </div>
            )}
            {children}
            <footer className="page-footer">
              <ProofLoopMark />
              <p>
                Verification covers the executed suite. It does not establish
                universal security.
              </p>
            </footer>
          </div>
        </main>
      </div>
    </Tooltip.Provider>
  );
}
