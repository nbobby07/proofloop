# ProofLoop product dashboard

From this directory:

```powershell
npm ci
npm run dev
```

Open http://localhost:5173. The initial view is explicitly labeled fixture preview.
Choose Live backend to use the canonical API at VITE_API_BASE_URL (default
http://localhost:8000). Start verification schedules authorized LedgerLite work;
it is not a visual replay. The scaffold backend currently returns 501 for planned
execution routes, which the dashboard displays without falling back to fixtures.

Arena: red/blue team evidence, independent lifecycle, verifier counts, diff and
report. Analytics: actual /api/analytics response only. History: observed live runs
in this browser session. Integrations: honest readiness and optional review/audio
components awaiting approved routes. No client-side provider credentials.

`npm run build` includes TypeScript compilation. `npm run lint` runs ESLint.
No tests or smoke tests are created or run by this work.

See [Developer A handoff](DEVELOPER-B-HANDOFF.md) for exact API/metadata proposals,
adapter setup, pending sponsor access, checks and limitations.
