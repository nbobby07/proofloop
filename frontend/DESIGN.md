# ProofLoop design specification

## Direction

An evidence review workspace for security engineers. The visual identity comes
from the authorization boundary: a principal, a ruled boundary and a protected
object. The hexagonal loop mark and connected pipeline use the same precise
line geometry. Titles describe actual work: Security verification, Attack
reproduction, Patch & remediation, Security evidence, Event stream.

## Palette and shape

| Role | Color | Application |
|---|---|---|
| Canvas | #0E1115 | Quiet graphite background |
| Navigation | #0C0E12 | Persistent application shell |
| Panel | #15191E | Evidence surfaces |
| Structure | #2A3039 | Fine separators and boundaries |
| Primary text | #E7E9EF | Warm neutral foreground |
| Secondary text | #9AA3B2 | Context, timestamps and labels |
| Action | #ACBDF5 | Primary action and selected navigation |
| Attack | #F0A09A | Reproduction and failed evidence |
| Defense | #A3B9ED | Patch proposals and remediation |
| Success | #91C9AA | Recorded passing outcomes |
| Incomplete / preview | #D6BD83 | Inconclusive or fixture labels |

Use 8px panel corners, 6px controls, 4px status tags and one-pixel rules.
These shapes repeat by function. The custom boundary graphic explains object
ownership. Large color fills are reserved for small semantic surfaces.

Typography uses locally available system sans with Inter when installed.
Use 32px desktop page headings (23px on phones), compact section headings, readable 12–13px working
text and monospace run IDs, diffs, HTTP status and timestamps. Metadata has
less emphasis than actions and results. Code is selectable. No font-network
dependency is required for the demo.

## Layout

Desktop: 216px navigation, 55px top bar, 32px content gutters. The workspace
context and explicit fixture/live switch remain above the run controls.

1. Page title and execution actions.
2. Current run identity and freshness.
3. Horizontal six-stage pipeline and a compact backend-verdict row.
4. Equal-width attack and remediation panels. Actual added lines preview the
   proposal; HTTP behavior is shown only when supplied.
5. Evidence inspector and chronological event stream. Accessible tabs switch
   between verification summaries, exact diff and saved report.

Analytics and history have separate pages. Optional audit tools live in Integrations; report-bound narration also appears
beside current evidence. At tablet widths the evidence panels stack; at phone widths
navigation becomes four equal items, the pipeline becomes two rows and the
arena panels stack. No controls disappear into clipped horizontal navigation.

## Psychology and interaction rationale

- Proximity groups the action, current run and its evidence, supporting scanning.
  The [NN/g proximity guidance](https://www.nngroup.com/articles/gestalt-proximity/)
  describes how nearby elements are perceived as related. This is a layout
  rationale, not evidence that this specific screen has been user-tested.
- Consistent control shapes and state treatments support recognition. A single
  emphasized start action establishes the first task; secondary actions retain
  lower visual weight. Detailed evidence is progressively disclosed in tabs.
- Color provides an additional signal. Text, icons, counts and status labels
  preserve meaning without hue, following [WCAG use of color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html).
- Green is reserved for recorded outcomes; blue distinguishes a proposal from
  a verdict. Explicit fixture and incomplete states help prevent overconfidence.
  These are product semantics, not universal claims that a color creates trust.
- Short event transitions communicate arrival; existing evidence does not move
  around continuously. Motion respects reduced-motion preferences.
- Dialogs manage focus, Escape and keyboard interaction. Scope information is
  available by keyboard. Chart values also appear in a semantic table.

## Libraries researched and selected

| Library | Use |
|---|---|
| [Radix UI](https://www.radix-ui.com/primitives/docs/overview/introduction) 1.7.0 | Unstyled accessible tabs, dialog, tooltip |
| [Lucide React](https://lucide.dev/guide/react/) 1.54.0 | Consistent stroke icon system |
| [Motion](https://motion.dev/docs/react-use-reduced-motion) 14.0.0 | Brief event-entry transitions respecting user settings |
| [Recharts](https://recharts.github.io/en-US/guide/) 3.10.1 | Lazy-loaded failure-family chart with exact accompanying table |
| [Vitest](https://vitest.dev/guide/) + [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/) | Trust-boundary and interaction checks |

[shadcn/ui](https://ui.shadcn.com/docs), Base UI and Shiki were evaluated.
Radix primitives provide the needed behavior while retaining the custom visual
language. A heavyweight editor is unnecessary for the current exact unified-diff
contract. React/TypeScript/Vite/Tailwind remain the required foundation.

## Evidence constraints

The merged backend API is live. Its analytics currently come from local run
storage; the UI does not label them ClickHouse SQL. ClickHouse/Guild remain unverified until connected. Report-bound ElevenLabs
playback was verified in the UI polish browser run. No fabricated chart series or integration
success states are introduced. A terminal run with no recorded stage completion
shows Not recorded, rather than implying a stage is still pending or succeeded.

## Acceptance

Readable desktop and 390px phone layouts; all navigation visible; source labeling
persists; keyboard tabs/dialog work; real API failures remain errors; accepted
rechallenge clears stale evidence; build/lint/contracts and relevant tests pass.
See VALIDATION.md for measured results and local runtime limits.


## UI and motion refinement — October 9, 2026

The frontend now uses a complete Discover → Report rail, an independent-verdict
strip, amber fixture results, retained recorded rounds and report-bound narration
beside the evidence. Navigation/evidence indicators share Motion layout identity;
150/220/320ms tokens and reduced-motion guards keep movement restrained. Current
results are withheld while Challenge Again is pending and invalidated after acceptance.
Recharts remains the analytics engine after evaluating Bklit registry installation.
See [UI-MOTION-POLISH.md](UI-MOTION-POLISH.md) for research, measured bundle impact,
actual execution receipts, matched screenshots and explicit validation limitations.
