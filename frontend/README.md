# ProofLoop product dashboard

From this directory:

```powershell
npm ci
npm run dev
```

Open http://localhost:5173. The initial view is explicitly labeled fixture preview.
Choose Live backend to use the canonical API at VITE_API_BASE_URL (default
http://localhost:8000). Start verification schedules authorized LedgerLite work;
it is not a visual replay. The integrated backend executes these routes when configured. Missing dependencies
and failed runs stay visible without falling back to fixtures.

Arena: red/blue team evidence, independent lifecycle, verifier counts, diff and
report. Analytics: actual /api/analytics response only. History: observed live runs
in this browser session. Integrations: honest readiness and optional review/audio
components awaiting approved routes. No client-side provider credentials.

`npm run build` includes TypeScript compilation. `npm run lint` runs ESLint.
The release was exercised in a real browser through model patching, independent
Docker verification, evidence display and rechallenge. See ../docs/RELEASE-INTEGRATION.md.

See [Developer A handoff](DEVELOPER-B-HANDOFF.md) for exact API/metadata proposals,
adapter setup, pending sponsor access, checks and limitations.
