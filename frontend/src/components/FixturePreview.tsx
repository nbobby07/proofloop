import fixtureJson from '../../../contracts/example-run.json'
import type { RunResponse } from '../types'

// JSON imports widen string literals. The backend contract test validates this exact file.
const fixture = fixtureJson as RunResponse

export function FixturePreview() {
  const suites = [
    ['Security', fixture.verification?.security_passed, fixture.verification?.security_total],
    ['Functional', fixture.verification?.functional_passed, fixture.verification?.functional_total],
    ['Adversarial', fixture.verification?.adversarial_passed, fixture.verification?.adversarial_total],
  ] as const

  return <section className="panel fixture-panel" aria-labelledby="fixture-title">
    <div className="panel-header">
      <div><p className="eyebrow">Interface preview</p><h2 id="fixture-title">{fixture.target}</h2></div>
      <span className="tag fixture-tag">FIXTURE · NO EXECUTION</span>
    </div>
    <p className="fixture-notice">Illustrative data for dashboard development. No scan, attack, patch, or verification has run.</p>
    <div className="finding-row">
      <div><p className="eyebrow">Example finding · {fixture.finding?.id}</p><h3>{fixture.finding?.title}</h3></div>
      <span className="tag">{fixture.finding?.severity} · fixture</span>
    </div>
    <div className="suite-grid">
      {suites.map(([name, passed, total]) => <div className="suite" key={name}>
        <span>{name}</span><strong>{passed}<small> / {total}</small></strong><p>illustrative checks</p>
      </div>)}
    </div>
    <div className="timeline">
      <p className="eyebrow">Fixture timeline</p>
      <ol>{fixture.events?.map(event => <li key={event.event_id}>
        <span className="timeline-dot" aria-hidden="true" />
        <div><span className="event-stage">{event.stage.replaceAll('_', ' ')}</span><p>{event.message}</p></div>
      </li>)}</ol>
    </div>
    <details className="diff-preview"><summary>View illustrative patch diff</summary><pre>{fixture.patch?.diff}</pre></details>
    <p className="scope-note">Example lifecycle status: <code>{fixture.status}</code> · source: <code>{fixture.source}</code>. A real passing result would cover only the executed suite.</p>
  </section>
}
