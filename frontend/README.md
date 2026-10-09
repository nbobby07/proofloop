# ProofLoop product dashboard

From this directory:

```powershell
npm ci
npm run dev
```

Open http://localhost:5173. The initial view is explicitly labeled fixture preview.
Choose Live backend to use the canonical API at VITE_API_BASE_URL (default
http://localhost:8000). Start verification schedules authorized LedgerLite work;
it is not a visual replay. Developer A's security-engine branch is merged into
this feature branch. Execution requires A's configured Linux sandbox and provider
environment. Unconfigured execution remains a visible error without fixture fallback.

Arena: red/blue team evidence, independent lifecycle, verifier counts, diff and
report. Analytics: actual /api/analytics response only. History: observed live runs
in this browser session. Integrations: honest readiness and optional review/audio
components awaiting approved routes. No client-side provider credentials.

`npm run build` includes TypeScript compilation. `npm run lint` runs ESLint.
`npm test` runs interaction and API-boundary tests. See [validation](VALIDATION.md)
for results, supported backend environment and remaining live integration limits.

See [design specification](DESIGN.md) for the palette, layout, interaction rationale
and researched UI libraries. Reviewed desktop and phone previews are in `design/`.

See [Developer A handoff](DEVELOPER-B-HANDOFF.md) for exact API/metadata proposals,
adapter setup, pending sponsor access, checks and limitations.

The lead separately exercised the release through real model patching, Docker
verification and browser rechallenge. See [release receipt](../docs/RELEASE-INTEGRATION.md).
