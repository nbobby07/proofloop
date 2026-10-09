# Developer B backend integration handoff

The API v1 wire contract and generated TypeScript are unchanged. All execution routes now
exist on `feat/security-engine`. Health retains its original response. POST run/challenge
returns 202 promptly; poll run and cursor-based ordered events. Report is 409 until terminal.
Unknown run is 404. Errors are redacted ErrorResponse objects. Rechallenge invalidates the
previous verification immediately. Failed, inconclusive, and unavailable execution must be
visible; never render them as successful verification.

Keep the existing local preview data labeled fixture. Actual runs use source execution, even
when operating on synthetic LedgerLite data. Counts come from independent frozen-suite
execution. Provider calls, static scan absence, and preview data cannot establish verified.

No telemetry, reports, guild, or frontend production code was edited by the coordinator.
No contract changes are proposed. Download transport is still absent: report evidence IDs
are opaque references, not usable file paths or download URLs. Do not add unsupported links.

Configuration and actual runtime validation results will be recorded in docs/INTEGRATION.md.
Frontend integration should use feat/security-engine once pushed, preserving B's changes.
