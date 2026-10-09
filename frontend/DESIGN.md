# ProofLoop design specification

## Product direction

ProofLoop is a guided security investigation: **Find → Fix → Prove**. The default
view explains the problem, what changed, what the independent verifier recorded,
and the next useful action. The real backend verdict owns the outcome.

The old screen exposed actions, six lifecycle stages, attack/remediation panels,
counts and logs simultaneously. The redesign establishes one reading order and
moves advanced evidence into five predictable tabs. See [UX-REDESIGN.md](UX-REDESIGN.md)
for diagnosis, implementation, screenshots and measured acceptance evidence.

## Visual system

| Role | Color | Application |
|---|---|---|
| Canvas | #F5F4F0 | Warm stone workspace |
| Text | #1D252B | Headings and body |
| Secondary | #616B72 | Supporting context |
| Navigation | #222B31 | Quiet charcoal shell |
| Action | #424CC7 | Dominant next action, selected tabs |
| Failure | #A4473C | Reproduced vulnerability and rejection |
| Verified | #31654D | Recorded passing results |
| Incomplete | #856022 | Incomplete evidence and fixture preview |

Color supplements explicit text and icons. System sans type avoids a font-network
dependency; monospace is reserved for code and technical evidence. Body is 16px,
secondary text generally 14px, section headings 20px. The result headline scales
from 38px desktop to 32px phone. Presentation Mode uses a 54px desktop headline
and 21px explanatory text. Spacing follows an 8px rhythm with fine adjustments
for controls. Rules divide the narrative; containers serve comparisons and inputs.

## Information architecture

Navigation: Verification, History, Analytics, Integrations. Desktop navigation is
208px wide; phone navigation presents all four destinations. Source selection is
secondary, but fixture labeling always remains visible. The main content has a
comfortable maximum width and generous gutters.

- **First run:** product explanation, the supported LedgerLite synthetic target,
  Run security verification, and secondary View previous runs.
- **Running:** Find/Fix/Prove with one active phase, a plain-language description
  and current recorded activity. Exact lifecycle and metadata remain in Audit trail.
- **Complete:** outcome headline, state-specific next action, before/after evidence,
  recorded patch attempts and the scope of the verdict.
- **Inspector:** Overview, Code changes, Test results, Audit trail, Report. Counts
  link directly to Test results. Code preserves selectable exact unified diffs,
  filtering and line numbers. Report preserves evidence references/hashes and JSON.
- **History:** session-observed runs with last-observed statuses, plus a saved-run ID
  field. Opening a run fetches its current evidence; no backend listing is implied.
- **Presentation:** same run and tabs, enlarged outcome, quiet source labels, no
  sidebar. The actual diff and Challenge remain available. Escape exits, restores
  the previous view and returns focus to the presentation trigger.

## State and motion semantics

Verified, rejected, inconclusive, execution error, running and fixture states have
distinct copy and actions. Counters never determine a verdict. Starting a challenge
immediately withholds previous counts, report and narration, including in History
and Presentation Mode. A failed request reports the error and restores the known
snapshot. Accepted execution retains the existing stale-response guard.

Motion uses the existing Motion library and shared duration/easing tokens. Short
state-keyed transitions reveal meaningful changes. There are no looping decorative
animations, fake logs or percentage counters. CSS and Motion respect reduced motion.
Evidence tabs retain diff filter state while hidden panels remain semantically hidden.
Radix keyboard navigation, descriptive labels, focus rings and focus restoration
support inspection. Chart values also appear in a keyboard-accessible exact table.

## Evidence boundaries

LedgerLite is the supported synthetic target. Before/after copy uses actual evidence;
HTTP 200 is shown only when recorded, and no post-patch status is invented. Only
explicit executed round metadata establishes earlier failed attempts. Missing prior
diffs, assertions and provider status remain unavailable. Fixture mode is illustrative
and cannot execute. ClickHouse/Guild integration success is not inferred from UI.

No dependencies, backend algorithms, API contracts, verifier rules or provider
configuration changed in this redesign. Investigation and analytics views load lazily.
Historical UI motion rationale and measurements remain in
[UI-MOTION-POLISH.md](UI-MOTION-POLISH.md).
