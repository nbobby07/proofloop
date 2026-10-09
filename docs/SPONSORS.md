# Sponsor integration contracts

Every integration below is **PLANNED**. Setup makes no paid calls and installs no provider SDKs. Do not count a sponsor as functional until an actual request/CLI execution has succeeded and redacted evidence is saved.

| Integration | Role and boundary | Owner |
| --- | --- | --- |
| OpenAI (additional access) | Defensive patch proposals; never verdicts | A |
| AkashML | Bounded adversarial proposals using its OpenAI-compatible API | A |
| Semgrep | Real static scanning of original and patched source | A |
| ClickHouse | Event analytics and failure-pattern-driven challenge selection | B |
| Senso.ai | Shared development context and separately governed authoritative policies | A |
| Guild.ai | Official hosted security-evidence review agent | B |
| ElevenLabs (optional) | Spoken incident briefing grounded in completed evidence | B |
| Pi | Overall award sponsor; no technical access or integration required | None |

## Prepared Python interfaces

- `OpenAIDefender.generate_patch(source: SourceSnapshot, finding: Finding, feedback: list[str]) -> PatchProposal` in `backend/providers/openai_client.py`.
- `AkashAttacker.generate_challenges(target: str, policy: SecurityPolicy, previous_results: list[ChallengeResult]) -> list[ChallengeSpec]` in `backend/providers/akash_client.py`.
- `SemgrepScanner.scan_repository(workspace: Path) -> ScanResult` in `backend/providers/semgrep_client.py`.
- `SensoPolicyStore.retrieve_security_policy(query: str) -> SecurityPolicy` and `retrieve_policy_sources(policy_ids: list[str]) -> list[PolicySource]` in `backend/providers/senso_client.py`.
- `ClickHouseTelemetry.insert_security_events(events: list[SecurityEvent]) -> None`, `query_security_analytics(filters: AnalyticsFilters) -> AnalyticsResponse`, `query_failure_patterns(run_id: str) -> list[FailurePattern]` in `backend/telemetry/clickhouse.py`.
- `ElevenLabsNarrator.generate_incident_briefing(report: ReportResponse) -> AudioArtifact` in `backend/reports/elevenlabs.py`.
- Guild official integration is reserved in `guild/`; no speculative SDK/API is implemented.

These are `Protocol` declarations, not working clients. Future adapters must validate DTOs, bound request size/time/retries, redact secrets, and return explicit failure states. Missing credentials or provider failures cannot create synthetic success.

## AkashML and OpenAI

The [official AkashML introduction](https://akashml.com/docs/getting-started/introduction) documents OpenAI-compatible requests at `https://api.akashml.com/v1`. A future adapter should explicitly pass `AKASH_API_KEY`, that base URL, and a model available to the account. No model is selected or called in setup. OpenAI credentials and model selection remain server-side; install a chosen SDK only when implementing the defender.

## Semgrep and Guardian

Implement the actual [Semgrep CLI](https://semgrep.dev/docs/cli-reference) or supported scanning API with pinned rules. Normalize findings and preserve incomplete/error results. Guardian is development-time review and does not imply runtime scanning access. Verify Guardian availability separately; do not claim it ran because a plugin is listed.

## ClickHouse

Follow the chosen [official Python client documentation](https://clickhouse.com/docs/integrations/language-clients/python/intro). Preserve canonical event ids, UTC timestamps, lifecycle/source tags, and redacted metadata. Separate fixture data from actual execution telemetry. Query historical challenge-family failure rates with sample counts and select the next bounded challenge using a deterministic strategy. Record the analytical result and selection rationale in evidence; a telemetry dashboard alone does not satisfy this integration goal.

## Senso

Retain policy source ids, authoritative flag, revisions, and provenance. Never elevate project notes into application policy without explicit trusted designation. Missing/conflicting authoritative policies block policy-grounded verification. The [official CLI workflow](https://docs.senso.ai/docs/senso-cli) is optional and documented in DEVELOPMENT; no organization or remote content is created during setup.

## Guild and narration

Confirm the event's official Guild.ai product, agent hosting, and auth flow with sponsor staff before selecting an SDK. Acceptance requires a real hosted agent run using a redacted completed evidence packet, with an accessible review URL and execution record. It reviews evidence but cannot establish the security verdict.

ElevenLabs is optional. A briefing must state exactly what executed tests showed and their limitations, derived from an actual completed execution report. Its fixture mode must never be presented as a real incident. Neither integration should delay the core demo.
