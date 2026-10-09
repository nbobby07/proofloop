import type { ReactNode } from "react";
import type { ConnectionStatus } from "../hooks/useBackendHealth";
import { ConnectionBadge } from "./ConnectionBadge";
import { SourceBadge } from "./StatusBadge";

export type Page = "arena" | "analytics" | "history" | "integrations";
const pages: { id: Page; label: string; icon: string }[] = [
  { id: "arena", label: "Security arena", icon: "◈" },
  { id: "analytics", label: "Analytics", icon: "▥" },
  { id: "history", label: "Run history", icon: "◷" },
  { id: "integrations", label: "Integrations", icon: "⌘" },
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
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#arena" onClick={() => navigate("arena")}>
          <span className="brand-mark">↻</span>proofloop
          <span className="brand-period">.</span>
        </a>
        <span className="workspace-label">SECURITY WORKSPACE</span>
        <nav aria-label="Main navigation">
          {pages.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "nav-active" : ""}`}
              aria-current={page === item.id ? "page" : undefined}
              onClick={() => navigate(item.id)}
            >
              <span aria-hidden="true">{item.icon}</span>
              {item.label}
              {page === item.id && <span className="nav-marker" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-target">
          <span className="eyebrow">Authorized target</span>
          <strong>
            <span className="target-logo">L</span>LedgerLite
          </strong>
          <small>Financial API · BOLA scenario</small>
        </div>
        <div className="sidebar-footer">
          <span className="sidebar-shield">◇</span>
          <strong>Evidence over confidence.</strong>
          <p>Passing an executed suite does not prove universal security.</p>
          <span className="badge">Cyberdefense · 2026</span>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            <span className="muted">Workspace / </span>
            {pages.find((p) => p.id === page)?.label}
          </span>
          <div className="topbar-right">
            <ConnectionBadge status={status} />
            <span className="topbar-divider" />
            <span className="user-avatar">PL</span>
          </div>
        </header>
        <div className="content">
          <div className="mode-toolbar">
            <div className="mode-switch" role="group" aria-label="Data source">
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
                Live backend
              </button>
            </div>
            <SourceBadge fixture={fixture} />
          </div>
          {fixture && (
            <div className="notice">
              <span>◇</span>
              <div>
                <strong>Fixture preview</strong> — illustrative data from the
                frozen contract. No attacks, tests, patches, or sponsor calls
                were executed.
              </div>
            </div>
          )}
          {children}
          <footer className="page-footer">
            <span>
              <span className="brand-period">↻</span> ProofLoop · Autonomous
              Adversarial Security Verification
            </span>
            <span>Executed evidence defines the scope.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
