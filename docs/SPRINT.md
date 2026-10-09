# Hackathon sprint

Deadline: October 9, 2026, **4:30 PM Pacific**. Two developers, separate computers and branches. Prioritize a working loop over the number of integrations.

| Priority | Milestone | Owner | Status / acceptance |
| --- | --- | --- | --- |
| P0 | Shared foundation | Setup | Framework, contracts, branches, docs; validation in SETUP-RESULTS |
| P0 | Authorized LedgerLite baseline | A | PLANNED: reproduce one real BOLA finding and pass frozen functional tests |
| P0 | Isolated verification runner | A | PLANNED: no secrets/network, limits, immutable tests, explicit timeout failures |
| P0 | Deterministic patch loop | A | PLANNED: reject bad patch, verify corrected patch, retain both attempts |
| P0 | Execution dashboard | B | PLANNED: real run/events/report with source separation and errors |
| P1 | OpenAI defender + Akash attacker | A | PLANNED: validated outputs; real redacted requests and bounded challenge execution |
| P1 | Semgrep runtime scan | A | PLANNED: real CLI output for original and patch |
| P1 | ClickHouse adaptive challenges | B + A handoff | PLANNED: analytics influences next challenge and records rationale |
| P1 | Senso policy grounding | A | PLANNED: authoritative sources cited and enforced |
| P2 | Guild hosted evidence review | B | PLANNED: official hosted agent executes, review URL saved |
| P2 | Incident narration | B | PLANNED/optional: grounded in actual completed evidence |
| P0 | Demo video and submission | Both | PLANNED: accessible links, team contacts, accurate claims before deadline |

Suggested demo: baseline invoice access succeeds across users → initial incomplete fix fails an independent challenge → bounded retry fixes ownership enforcement → functional and adversarial suites pass → evidence and saved regression test explain the result's limits.

Coordinate early on target/policy/test manifest. A ships API behavior against frozen wire contracts; B can build with visibly labeled fixtures until execution exists. Cut optional narration and secondary integrations if they threaten a truthful working demonstration. Leave time for fresh clone validation and judge access checks.
