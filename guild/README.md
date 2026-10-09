# Guild evidence auditor — adapter implemented, hosting PLANNED

`PROMPT.md` defines the Native evidence auditor. `client.py` calls the actual
[Guild public conversations API](https://docs.guild.ai/api-reference/conversations).
No local function is presented as a Guild-hosted agent.

Use Guild's official CLI/UI to initialize a Native agent, then use this PROMPT.md.
Preserve the CLI-generated guild.yaml/config rather than guessing a deployment
manifest. Disable tools, external integrations and delegated agents. Current
[agent-type docs](https://docs.guild.ai/guide/agent-types) describe Native agents
with a managed loop and text input/output; typed code uses @guildai/agents-sdk if
needed later. No extra LLM API is required by this local adapter.

Publish/install the agent in the hackathon workspace using the official workflow.
Confirm sponsor access and model availability. Configure server-side GUILD_API_KEY
as the complete account key id:secret, GUILD_WORKSPACE_ID and GUILD_AGENT_ID.
Runtime permissions: sessions:write, workspaces:read and agents:read, subject to
account ownership and workspace restrictions. Credential creation/access changes
require action-time approval. Existing placeholders do not prove account access.

A constructs GuildClient(GuildConfig.from_env(), approved_for_export=True) after
approving redacted evidence export. start_audit(report, events) creates a genuine
hosted chat session; poll_audit(job) reads ordered events with an exclusive cursor.
Persist AuditJob through A's storage, schedule polling with a bounded deadline,
and preserve agent version, packet/report digest, raw validated review and session
identity. Do not blindly retry session creation after an uncertain timeout: reconcile
the hosted session first to avoid duplicate jobs/charges.

The packet includes a completed execution report and at most 500 matching events;
metadata is excluded. Oversize inputs are rejected, never silently summarized.
The producer must redact report/event strings before enabling export. Artifact
contents/manifests/source omitted by API v1 are declared missing, never inspected
by implication. Output must match run/digest and cite only supplied evidence IDs.
Review is advisory and never contains a new security verdict.

Proposed API for A: POST /api/runs/{id}/audit schedules; GET returns job status,
validated review, packet/report digest, agent/session/version and a real review URL.
Obtain the URL from Guild UI/API; the adapter does not fabricate a share link.
The frontend accepts a verified app.guild.ai review URL once that contract exists.

Mark Active only after a hosted completion and an accessible execution record.
Unit tests pass for evidence packets, citation/digest validation and export approval.
No Guild deployment or hosted request has run in this work.
