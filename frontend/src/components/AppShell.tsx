import type { ReactNode } from "react";
import { Tooltip } from "radix-ui";
import type { ConnectionStatus } from "../hooks/useBackendHealth";
import { ConnectionBadge } from "./ConnectionBadge";
import { Icon, ProofLoopMark } from "./Icon";
import type { IconName } from "./Icon";

export type Page = "arena" | "analytics" | "history" | "integrations";
const pages: { id: Page; label: string; icon: IconName }[] = [
  { id: "arena", label: "Verification", icon: "arena" },
  { id: "analytics", label: "Analytics", icon: "analytics" },
  { id: "history", label: "Run history", icon: "history" },
  { id: "integrations", label: "Integrations", icon: "integrations" },
];
export function AppShell({
  page,
  navigate,
  fixture,
  setFixture,
  status,
  children,
}: {
  page: Page;
  navigate: (page: Page) => void;
  fixture: boolean;
  setFixture: (fixture: boolean) => void;
  status: ConnectionStatus;
  children: ReactNode;
}) {
  return (
    <Tooltip.Provider delayDuration={300}>
      <div className="app-shell">
        <aside className="sidebar">
          <a className="brand" href="#arena" onClick={() => navigate("arena")}>
            <ProofLoopMark />
            <span>ProofLoop</span>
          </a>
          <div className="workspace-selector">
            <span className="workspace-avatar">P</span>
            <div>
              <strong>ProofLoop workspace</strong>
              <small>Cyberdefense Hackathon</small>
            </div>
          </div>
          <span className="workspace-label">WORKSPACE</span>
          <nav aria-label="Main navigation">
            {pages.map((item) => (
              <button
                key={item.id}
                className={`nav-item ${page === item.id ? "nav-active" : ""}`}
                aria-current={page === item.id ? "page" : undefined}
                onClick={() => navigate(item.id)}
              >
                <Icon name={item.icon} />
                {item.label}
              </button>
            ))}
          </nav>
          <div className="sidebar-target">
            <span className="workspace-label">TARGET APPLICATION</span>
            <div className="target-entry">
              <span className="target-logo">L</span>
              <div>
                <strong>LedgerLite</strong>
                <small>Financial API</small>
              </div>
              <span className="target-scope">Local</span>
            </div>
          </div>
          <div className="sidebar-footer">
            <Icon name="shield" />
            <div>
              <strong>Independent verification</strong>
              <p>Verdicts come from executed tests.</p>
            </div>
          </div>
        </aside>
        <main>
          <header className="topbar">
            <div className="breadcrumbs">
              <span>Workspace</span>
              <Icon name="chevron" />
              <strong>{pages.find((p) => p.id === page)?.label}</strong>
            </div>
            <div className="topbar-right">
              <ConnectionBadge status={status} />
              <span className="topbar-divider" />
              <span className="environment-label">Development</span>
            </div>
          </header>
          <div className="content">
            <div className="workspace-toolbar">
              <div className="workspace-location">
                <Icon name="target" />
                <span>LedgerLite</span>
                <span className="muted">/</span>
                <span className="muted">Authorization</span>
              </div>
              <div
                className="mode-switch"
                role="group"
                aria-label="Data source"
              >
                <button
                  aria-pressed={fixture}
                  className={fixture ? "selected" : ""}
                  onClick={() => setFixture(true)}
                >
                  Fixture preview
                </button>
                <button
                  aria-pressed={!fixture}
                  className={!fixture ? "selected" : ""}
                  onClick={() => setFixture(false)}
                >
                  <span className="dot" />
                  Live
                </button>
              </div>
            </div>
            {fixture && (
              <div className="fixture-banner">
                <Icon name="info" />
                <strong>Fixture preview</strong>
                <span>
                  Illustrative contract data. No attacks or tests have been
                  executed.
                </span>
              </div>
            )}
            {children}
            <footer className="page-footer">
              <span>ProofLoop</span>
              <span>
                Verification is scoped to the executed suite. It does not
                establish universal security.
              </span>
            </footer>
          </div>
        </main>
      </div>
    </Tooltip.Provider>
  );
}
