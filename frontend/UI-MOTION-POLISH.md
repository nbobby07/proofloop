# ProofLoop UI and motion polish — October 9, 2026

Implemented on `feat/ui-motion-polish`, isolated from existing checkouts, based on
`origin/main` at `6f6bf79b7185f51523525822cf0ff573576d7fb6`. All changes are frontend-owned.
A 50-minute implementation/validation budget was set at 1:33 PM Pacific to leave
hackathon submission time before 4:30 PM. No merge or submission is performed here.

## Design changes

- Stronger 32px desktop type hierarchy, quieter graphite surfaces, numbered review
  sections, a restrained coral punctuation accent, and deliberate control/surface radii.
- Discover → Reproduce → Patch → Verify → Challenge → Report is the primary rail.
  Retry is a patch-stage state; receiving a saved report completes the Report stage.
  Stage completion means recorded lifecycle evidence, not a passing security verdict.
- The current independent verdict has its own visual hierarchy. Fixture verdicts and
  fixture counts use amber and explicit illustrative wording rather than green success.
- The principal/object diagram is labeled a schematic. Its boundary emphasizes a
  recorded reproduced baseline. It no longer invents names or object identifiers.
  Baseline HTTP status and messages come directly from the current run and events.
- Actual added lines preview the current proposal; exact additions, deletions, line
  numbers and selectable unified diff remain available in Code changes. The filter
  survives tab switches. Long code scrolls inside its panel.
- Verification explicitly distinguishes pending counts, zero checks, recorded passing
  counts and counts that are not all passing. Recorded rounds retain the failed first
  attempt, later attempts, and fresh challenges with their execution identifiers.
- Clicking Challenge Again withholds the old current verdict/counts/report/audio while
  the API request is pending. Rejected requests retain the known snapshot and error.
  Accepted requests preserve the existing stale-snapshot guard until fresh completion.
  Prior pipeline stages are labeled Earlier cycle after the recorded invalidation.
- Event arrival is keyed by event ID; metadata expands through interruptible height
  motion. Filtering and poll updates do not remount the entire workspace.
- Incident narration is available alongside the current evidence and in Integrations.
  Its existing report-hash checks, generation, native media controls, play/pause/replay,
  transcript and errors remain intact. Invalidating the report unmounts its audio.
- Analytics uses a consistent 0–100% failure-rate axis, an exact numerator/denominator
  tooltip, compact metric separators and its original exact numerical table. Rates
  derive solely from backend responses. Zero-round tooltips say rate unavailable.
- Tablet evidence panels stack and the pipeline becomes two rows; mobile retains all
  four navigation controls, all run actions, selectable diffs and scrolling tables.

## Motion and libraries

The existing React, Motion 14, Radix UI 1.7, Lucide React and Recharts 3.10.1 are used.
No application dependency, lockfile, hosted font or paid service was added.

Shared CSS/JS motion tokens: 150ms micro, 220ms panel and 320ms major state changes;
cubic-bezier(0.22, 1, 0.36, 1), no overshoot. Motion LayoutGroup/layoutId drives nav and
active evidence-tab selection. AnimatePresence handles metadata expansion only;
security verdicts have no exit interval that could leave stale success on screen.
MotionConfig respects the user preference; useReducedMotion zeroes state durations,
and CSS disables animations/transitions under prefers-reduced-motion.

Research sources:

- [Bklit](https://bklit.com/), [docs](https://bklit.com/docs),
  [installation](https://bklit.com/docs/installation),
  [bar charts](https://bklit.com/docs/components/bar-chart) and
  [tooltips](https://bklit.com/docs/utility/tooltip): focused labels, restrained chart
  chrome and precise data explanations. Installing registry components requires a
  shadcn setup; the benefit did not justify that architectural/dependency change.
  Retained Recharts and refined compatible presentation. No Bklit source copied.
- [Motion React](https://motion.dev/docs/react) and
  [layout animation](https://motion.dev/docs/react-layout-animations): shared-element
  indicators, stable layout identity, state-bound transitions.
- [Transitions.dev](https://transitions.dev/): named timing tokens, explicit animated
  properties, short disclosure/tab transitions and reduced-motion guards.
- [Godly](https://godly.design/): stronger typography and distinctive composition,
  adapted as an evidence workspace rather than a marketing page.
- [Animos](https://animos.app/) was inspected in the browser for template-based
  showcase framing after its text fetch returned no content. It was not installed
  or used as an application dependency.
- [Deck.gallery](https://deck.gallery/): concise storytelling and clear hierarchy.
  No paid material, branded designs or proprietary source was copied.

## Automated validation

| Check | Result |
| --- | --- |
| Frontend lint | Passed without warnings |
| TypeScript, `npm run typecheck` | Passed |
| Frontend tests | 21 passed across 4 files |
| Production build | Passed |
| Python schema export `--check` | Contracts current |
| TypeScript contract regeneration + Git diff | No drift |
| Lockfile / dependency changes | None |
| `git diff --check` | Passed |

New tests cover fixture/unknown/unexecuted outcome labels, retention of a failed
attempt next to later passing rounds, prior-cycle labeling during challenge, diff
filter retention, and pending-challenge rejection recovery. Existing source checks,
API errors, pagination ordering, accepted rechallenge invalidation, persistence and
keyboard/dialog tests still pass. Test doubles are not execution receipts.

## Actual browser acceptance

Browser: Codex in-app browser; frontend `http://127.0.0.1:5176`. A temporary Vite
same-origin proxy targets the existing backend `http://127.0.0.1:8001`, because the
backend CORS configuration does not allow the new frontend port. This setup exists
only in the validation process; neither Vite configuration nor backend files changed.

Created `run_b79f04fcd8114bf7b215a49e4286175e` through the Start verification control.
The actual backend reproduced HTTP 200 baseline access, rejected patch attempt 1,
and verified attempt 2 on 6/6 security, 22/22 functional and 16/16 adversarial checks.
Three recorded rounds were retained before rechallenge. The completed report had
14 evidence references. Real ElevenLabs audio was generated and browser play,
pause, replay and transcript controls were exercised.

Challenge Again visibly replaced the current result with Challenging, three pending
suite counts and no audio element. Historical failed/passing rounds remained
inspectable. The old report's audio URL returned HTTP 409. Fresh independent execution
completed another 44/44 round; event count became 40 and the report had 19 references.
See [the actual API receipt](design/polish/live-acceptance.json).

Browser evidence tabs, the exact current patch, saved report references, history,
integration states and analytics were inspected. Right-arrow keyboard navigation
moved Code changes to Evidence report. Escape closed the saved-run dialog and returned
focus to its trigger. The analytics tooltip showed 3 unsuccessful/incomplete rounds
out of 12, 25.0%, matching the exact backend table at inspection time.

| Viewport | Document width | Result |
| --- | --- | --- |
| 1440px | 1440px | No page overflow; side-by-side attack/remediation and review rail |
| 1280px | 1280px | No page overflow; all run actions visible |
| 768px | 768px | No page overflow; stacked evidence and two-row pipeline |
| 390px | 390px | No page overflow; all four nav and three live actions visible |

Measurements and control widths are in [responsive.json](design/polish/responsive.json).
Diffs and numerical tables intentionally allow internal horizontal scrolling.

## Screenshots and comparison

The baseline preview server uses frontend source identical to origin/main; Git diff
confirmed no source or dependency differences. Both matched comparisons use the same
labeled fixture and the same viewport dimensions. Live screenshots are separate.

| View | Before | After |
| --- | --- | --- |
| Fixture, 1440px | [Before](design/polish/before-desktop.jpg) | [After](design/polish/after-fixture-desktop.jpg) |
| Fixture, 390px | [Before](design/polish/before-mobile.jpg) | [After](design/polish/after-fixture-mobile.jpg) |
| Live desktop | — | [Recorded rounds expanded](design/polish/after-desktop.jpg) |
| Live laptop | — | [1280px](design/polish/after-1280.jpg) |
| Live tablet | — | [768px](design/polish/after-768.jpg) |
| Live mobile | — | [390px](design/polish/after-390.jpg) |
| Fresh challenge | — | [In progress](design/polish/challenge-in-progress.jpg) |
| Analytics | — | [Actual tooltip and table](design/polish/analytics-desktop.jpg) |

Compared with baseline: stronger run and verdict hierarchy; distinctly styled attack
and remediation panels; truthful amber fixture treatment; explicit review context;
larger legible event metadata controls; complete workflow including Report. The
underlying evidence and source labeling remain visible.

## Bundle impact

Measured Vite builds against the unchanged dependency lock. Units are Vite kB.

| Asset | Before raw / gzip | After raw / gzip | Gzip change |
| --- | --- | --- | --- |
| Main JavaScript | 481.48 / 154.28 | 493.96 / 157.24 | +2.96 kB, about 1.9% |
| Lazy analytics JavaScript | 361.36 / 104.94 | 361.98 / 105.08 | +0.14 kB |
| CSS | 33.91 / 8.70 | 42.49 / 10.52 | +1.82 kB |

Analytics remains lazy-loaded. Screenshots/documentation are not imported into the
application bundle. No additional perpetual animation was introduced.

## Files changed

- App.tsx and components/AppShell.tsx: global motion preference, nav indicator, skip link.
- components/motion.ts and index.css: shared motion/design tokens and responsive styling.
- pages/Dashboard.tsx and execution/useRun.ts: expose the pending action, withhold old
  challenge evidence, place narration in the review rail; execution semantics unchanged.
- execution/RunControls.tsx and SecurityArena.tsx: run hierarchy, challenge lifecycle,
  recorded pipeline, schematic boundary and proposal presentation.
- execution/EventStream.tsx, RecordedRounds.tsx and lifecycle.ts: expandable metadata,
  recorded outcome labels and retained rounds.
- evidence/EvidenceReport.tsx: shared tab indicator, stable diff filter and suite context.
- analytics/AnalyticsDashboard.tsx: exact rate axis/tooltip and metric layout.
- briefing/BriefingPanel.tsx and IncidentBriefingPlayer.tsx: integrated report narration.
- test/presentation.test.tsx and test/useRun.test.tsx: evidence presentation regressions.
- DESIGN.md, VALIDATION.md, this report and design/polish/: frontend-owned documentation,
  actual screenshots and validation receipts.

## Known limitations

- API v1 exposes only the current patch diff and suite summary counts. Earlier diffs,
  individual test assertions and raw HTTP request/response bodies are not supplied.
  Historical rounds, hashes, IDs and saved references are retained without inventing
  those missing details. The authorization graphic is explicitly a schematic.
- Reduced-motion guards were checked in source; browser emulation is not exposed by
  the available in-app browser capability. No browser reduced-preference acceptance
  is claimed, and the user's global system preference was not changed.
- Browser validation used the development frontend plus a production build check,
  not a deployed production site. API failure/rejection cases are covered by unit
  tests; no live backend failure was deliberately induced.
- This task does not validate ClickHouse/Guild/other provider integrations, universal
  security, FPS performance, or a complete assistive-technology audit.
- Review and CI are required before merge. The branch remains unmerged.
