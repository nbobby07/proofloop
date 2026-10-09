import { ConnectionBadge } from '../components/ConnectionBadge'
import { FixturePreview } from '../components/FixturePreview'
import { useBackendHealth } from '../hooks/useBackendHealth'
import { API_BASE_URL } from '../services/api'

const pipeline = ['Discover', 'Reproduce', 'Patch', 'Verify', 'Challenge']

export function Dashboard() {
  const { status, error, retry } = useBackendHealth()
  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#workspace" aria-label="ProofLoop home"><span className="brand-mark" aria-hidden="true">↻</span>ProofLoop</a>
      <p className="sidebar-label">Workspace</p>
      <a className="nav-active" href="#workspace"><span aria-hidden="true">◈</span> Overview</a>
      <div className="sidebar-footer"><span className="tag">FOUNDATION</span><p>Cyberdefense Hackathon<br />October 9, 2026</p></div>
    </aside>
    <main id="workspace">
      <header className="topbar"><span>Verification workspace <span className="muted">/ Overview</span></span><ConnectionBadge status={status} /></header>
      <div className="content">
        <div className="hero"><div><p className="eyebrow">Proof, before confidence.</p><h1>Security that shows<br />its work.</h1><p className="subtitle">Autonomous adversarial security verification.</p></div><div className="hero-note"><span className="tag">SETUP PHASE</span><p>The foundation is ready.<br />The security engine is planned.</p></div></div>
        <section className="panel principle"><span className="principle-icon" aria-hidden="true">◎</span><div><h2>Independent verification is the verdict.</h2><p>Agents propose attacks and fixes. Executed tests and deterministic rules decide whether a patch passes.</p></div></section>
        <section className="pipeline" aria-label="Planned execution pipeline">{pipeline.map((stage, index) => <div key={stage}><span className="step-number">0{index + 1}</span><strong>{stage}</strong><span className="planned-label">PLANNED</span></div>)}</section>
        <div className="dashboard-grid"><FixturePreview /><div className="right-column">
          <section className="panel"><p className="eyebrow">Live infrastructure</p><h2>Backend health</h2><p className="body-copy">The health check is the only active API operation.</p><dl className="health-details"><dt>Endpoint</dt><dd><code>/api/health</code></dd><dt>Server</dt><dd><code>{API_BASE_URL}</code></dd></dl>{error && <p className="error-message" role="alert">{error}</p>}<button onClick={retry} disabled={status === 'checking'}>Refresh connection <span aria-hidden="true">↗</span></button></section>
          <section className="panel"><p className="eyebrow">Execution status</p><h2>Awaiting the engine</h2><p className="body-copy">Run creation and challenges will be available after isolated execution and evidence collection are implemented.</p><button disabled>Start security run <span aria-hidden="true">→</span></button><p className="scope-note">Sponsor integrations are planned. No paid API calls are made in this scaffold.</p></section>
        </div></div>
        <footer className="page-footer"><span>ProofLoop · Development foundation</span><span>Passing a suite does not prove universal security.</span></footer>
      </div>
    </main>
  </div>
}
