# Guided investigation redesign

## Baseline and delivery

Stacked on PR #6 at 9f617ca7ae05cadd7f9b19d74c4d2de0b4d2bd80. On October 9 at
1:59 PM Pacific it was open, CI passed, and review was still required. PR #6 and
its worktree are preserved. Review/merge #6 first; the new PR targets main and
Git will then show only the additional redesign. The stable release remains available.
Initial implementation/validation timebox: 60 minutes, leaving submission time.

## A. Diagnosis

Dashboard mounts run controls, pipeline, two team panels, evidence and event stream
simultaneously. AppShell repeats workspace, target, environment and source context.
RunControls gives three actions similar prominence. SecurityArena leads with six
backend stages and raw scanner titles. EvidenceReport opens dense suite counts by
default. index.css compresses most working text to 10–13px. The result is accurate
but lacks a reading order and a clear next action.

## B. Journey and information architecture

1. **Start** — explain ProofLoop, show the one supported synthetic target, and offer
   Run security verification. History is secondary. New sessions default to live mode;
   explicit fixture preview stays visibly labeled and cannot execute operations.
2. **Investigate** — Find → Fix → Prove. Emphasize one active phase and plain-language
   current activity. Preserve exact states, ordered events and metadata in Audit trail.
3. **Understand the result** — one outcome headline, concise explanation, before/after
   evidence and a sequence of recorded attempts. Verified → Challenge this fix;
   rejected → Inspect failed checks; incomplete/error → Inspect evidence or retry fetch.
4. **Inspect** — five predictable tabs: Overview, Code changes, Test results, Audit
   trail and Report. Counts expand through Test results; diff and report retain exact
   backend content and export. History owns opening a saved run by ID.
5. **Present** — the same selected run in a focused, larger view. Hide navigation,
   retain source labels, patch access and Challenge. Escape exits and returns focus.

Normal layout sketch:

    dark navigation  |  Verification               Data source
                     |  LedgerLite investigation   Present / New
                     |  Overview  Code  Tests  Audit  Report
                     |
                     |  VERDICT
                     |  One clear outcome headline
                     |  Why this outcome was recorded
                     |  [ One primary action ]   secondary link
                     |
                     |  Before                 After
                     |  Recorded attempt sequence
                     |  Scope of this result

First-run replaces the entire investigation area with a welcome and supported-target
explanation. Technical sections are not rendered as empty dashboard panels.

## Design rationale

Warm stone #F5F4F0, ink #1D252B and a quiet charcoal navigation establish an editorial
reading surface. Indigo identifies the next action; coral marks reproduced failures,
green recorded passing results, amber incomplete/fixture evidence. Use color plus
text/icons. Comfortable 16px body, 14px metadata, 20px section headings and 36px result
headings replace tiny labels. Rules separate stories; containers are reserved for
actual comparisons, code and interaction surfaces. No hosted fonts or new libraries.

The first screen should answer what happened, why it matters, and what to do next.
This is an interaction-design hypothesis checked through task walkthroughs, not a
claim that independent human usability research has been performed.

## Evidence rules

Never derive a verdict from counters. Only the backend status can establish Verified.
Counts in a verified headline come from its current verification summary. Incomplete
counts remain incomplete. An earlier failed round must be explicit executed/fail
metadata before it is described as failed independent testing. Attempt history uses
recorded events; missing earlier attempts are not reconstructed. No invented HTTP
response, percentage progress, granular assertion, prior diff or supported repository.
Pending Challenge immediately withholds old results; accepted challenge retains the
existing stale-snapshot guard. Narration remains bound to the current report identity.

## C–E. Implemented changes

| Surface | Completed change |
|---|---|
| AppShell | Quiet navigation, secondary source selector, persistent fixture banner, presentation shell |
| Welcome | Clear product explanation, supported target, one start action |
| InvestigationWorkspace / model | Five evidence tabs, lifecycle mapping, evidence-derived attempt history and result copy |
| SecurityArena / RunControls | Narrative result, before/after comparison, active phase, state-specific primary action |
| EvidenceReport / EventStream | Exact diff, test provenance, ordered expandable events, references and report export |
| Dashboard / useRun | First-run orchestration, lazy investigation, presentation/focus state, immediate pending-challenge masking; existing engine unchanged |
| SecurityHistory | Saved-run lookup and session history with last-observed status labels |
| IncidentBriefingPlayer | Existing report-bound playback; captured audio element is paused when detached/invalidation occurs |
| Analytics / Integrations | Readable light chart theme, focusable exact table, honest availability copy |
| index.css | Warm editorial visual system, responsive layout, readable type, restrained state transitions |

Presentation Mode is implemented and browser-tested using real run data. All five
evidence tabs remain available; the sidebar and completed phase rail disappear.
The current outcome, attempts and scoped counts fit the tested 1440p viewport.
Challenge uses the same live handler. Escape restores the prior view and trigger focus.

## F. Automated validation

All checks passed after the final source edits on October 9, 2026:

- `npm run lint`: pass, no warnings.
- `npm run typecheck`: pass.
- `npm test`: **26 passed across 6 files**.
- `npm run build`: pass, no large-chunk warning.
- `python -m scripts.export_contracts --check`: current.
- TypeScript contract regeneration: no diff in generated types.
- No changes to package.json, package-lock.json, schemas or backend/security code.

Tests cover first-run action hierarchy, fixture safety, real request failures,
keyboard inspector navigation and retained diff filters, exact evidence-derived
copy, incomplete versus verified outcomes, presentation restoration, pending
challenge masking in Overview/Presentation/History, and pausing detached audio.
A separate test uses the real Motion path with a mocked reduced-motion media query.
Existing polling, stale-response and API boundary tests continue to pass.

### Bundle measurement

Vite production output, gzip kB (not a runtime benchmark):

| Asset | PR #6 baseline | Redesign |
|---|---:|---:|
| Initial main JS | 157.24 | 147.23 |
| Investigation JS loaded on demand | included above | 14.15 |
| Analytics JS loaded on demand | 105.08 | 105.09 |
| Main CSS | 10.52 | 9.82 |

Initial JS decreases 10.01 kB gzip. Main plus investigation totals 161.38 kB gzip,
4.14 kB more than the former main. No new libraries or remote fonts were added.
No frame-rate, interaction-latency or production-user performance measurement is claimed.

## Actual browser evidence

Test frontend: http://127.0.0.1:5192, runtime-only proxy to the existing backend at
http://127.0.0.1:8001. This proxy is local validation setup, not a committed deployment
configuration. Baseline PR #6 and its checkout remain available as a fallback.

1. **Fresh first-run flow:** clicked Run security verification for LedgerLite. Run
   `run_e1d06c5c91c34b3793fbff7674d28a2c` reproduced unauthorized access with recorded
   HTTP 200. Three actual proposals failed; the terminal verdict was **Rejected**.
   Current counts: security 0/6, functional 16/22, adversarial 15/16 (31/44 passing).
   The UI showed the rejected headline and Inspect failed checks, not a success.
2. **Verified result:** opened saved execution
   `run_b79f04fcd8114bf7b215a49e4286175e` through History. The UI showed the recorded
   first rejected attempt and second verified attempt, with 6/6, 22/22 and 16/16.
   Exact diff/filter/line numbers, test results, audit metadata and report were inspected.
3. **Export:** browser-download JSON was exactly equal to the backend report at
   download time, with 19 evidence references. Later challenge changes the report.
4. **Narration:** generated actual report-bound ElevenLabs briefing; exercised
   Play, Pause, Replay and transcript. Started playback, entered Presentation Mode
   and challenged the fix. Old audio was removed immediately, counts became dashes,
   and the current attempt became Under challenge. The old audio endpoint returned
   **409**. The captured audio element is also paused on teardown in a focused test.
5. **Fresh challenge:** the saved run completed a new independent round
   `event_00000043` with **44/44** passing checks. Its event count increased from
   40 to 46. This is a real fresh challenge, distinct from the rejected new run above.
6. **Presentation and keyboard:** reviewed the actual patch, used arrow navigation
   between evidence tabs and Escape to exit with focus restored. At 2560×1440,
   the main headline is 54px and the attempt sequence ends at approximately 947px.
7. **Fixture and secondary pages:** source controls work on phone; fixture is
   labeled illustrative and offers Use live backend rather than execution. Analytics
   showed 4 runs (3 verified, 1 rejected), with keyboard-accessible chart and exact
   table. Integrations retained explicit unverified/unavailable status descriptions.

Machine-readable receipts: [live acceptance](design/redesign/live-acceptance.json)
and [responsive measurements](design/redesign/responsive.json).

### Responsive and accessibility observations

| Viewport width | Document width | Body | Main result heading |
|---|---:|---:|---:|
| 1440px | 1440px | 16px | 38px |
| 1280px | 1280px | 16px | 36px |
| 768px | 768px | 16px | 36px |
| 390px | 390px | 16px | 32px |

No page-level horizontal overflow at these widths. On the 390×844 first-run view,
the Run security verification button spans y=672–718px, inside the initial viewport.
All main destinations and inspector tabs remain available. Code retains its own
horizontal scrolling where required. Focus states, source controls, tabs and errors
were checked through keyboard/DOM/browser walkthroughs. Color is supplemented by
words and icons. Reduced-motion CSS and the actual Motion test pass; a browser OS
preference test and a full screen-reader/contrast audit were not performed.

## Before and after

Screenshots capture actual browser output, not mockups. Before uses PR #6; after uses
this branch. The result captures use the same saved execution; some were captured
before versus after its fresh challenge, so event totals can differ legitimately.

| View | Before | After |
|---|---|---|
| Desktop result | [PR #6](design/redesign/before-desktop.jpg) | [Redesign](design/redesign/after-desktop.jpg) |
| Phone result | [PR #6](design/redesign/before-mobile.jpg) | [Redesign](design/redesign/after-390.jpg) |
| First run | — | [Desktop](design/redesign/welcome-desktop.jpg), [phone](design/redesign/welcome-mobile.jpg) |
| Rejected result | — | [Real rejected execution](design/redesign/rejected-desktop.jpg) |
| Presentation | — | [1440p](design/redesign/presentation-1440p.jpg), [fresh challenge](design/redesign/challenge-presentation.jpg) |
| Other widths | — | [1280px](design/redesign/after-1280.jpg), [768px](design/redesign/after-768.jpg) |
| Fixture / analytics | — | [Labeled phone fixture](design/redesign/fixture-mobile.jpg), [phone analytics](design/redesign/analytics-mobile.jpg) |

The desktop result now leads with one large verdict and action. Detailed code and
logs have their own views; they no longer compete with the result. Phone content
follows the same narrative instead of shrinking a multi-panel engineering dashboard.

## Remaining UX limitations

- Five-second comprehension was evaluated as a design walkthrough, not an independent
  human study. Projector hardware and screen-reader behavior were not directly tested.
- History contains runs observed in the current browser session plus saved-ID lookup;
  the API does not offer a full run-list endpoint. Refreshing can lose session history.
- The backend exposes suite counts/round provenance, not individual assertion details,
  earlier patch diffs or a post-patch HTTP response. The UI does not reconstruct them.
- Starting a new autonomous run can legitimately fail every proposal, as this test did.
  For a presentation of both failed and successful attempts, open the saved verified
  run above, then execute Challenge if desired. This is saved real evidence, not a replay
  simulation or a guarantee of future generation success.
- The scope remains LedgerLite and its frozen executed suite. No arbitrary repository
  support, universal security or unverified sponsor integration is implied.
- Broad analytics/settings redesign and a production deployment are outside this
  frontend change. The current stable release and PR #6 remain the fallback.

## Review and handoff

The redesign branch is stacked on the exact PR #6 head documented above. At the
final pre-PR check on October 9, PR #6 was **approved and still open**, unchanged at
`9f617ca7ae05cadd7f9b19d74c4d2de0b4d2bd80`. Merge #6 before this PR to keep review
incremental. This work does not merge either PR or bypass repository review.
