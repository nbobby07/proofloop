import type {
  AnalyticsResponse,
  ChallengeResponse,
  EventsResponse,
  HealthResponse,
  ReportResponse,
  RunResponse,
  RunStatus,
  SecurityEvent,
} from "../types";

export const statuses: RunStatus[] = [
  "pending",
  "discovering",
  "reproducing",
  "generating_patch",
  "applying_patch",
  "verifying",
  "challenging",
  "retrying",
  "verified",
  "rejected",
  "inconclusive",
  "error",
];
const eventTypes = [
  "stage_started",
  "stage_completed",
  "finding_discovered",
  "baseline_reproduced",
  "patch_proposed",
  "patch_applied",
  "test_completed",
  "challenge_proposed",
  "retry_scheduled",
  "run_completed",
  "run_failed",
];
const fail = (): never => {
  throw new Error("Invalid contract payload");
};
const object = (v: unknown): Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : fail();
const string = (v: unknown, max = 5000): string =>
  typeof v === "string" && v.length > 0 && v.length <= max ? v : fail();
const id = (v: unknown): string =>
  /^[A-Za-z0-9_-]{1,128}$/.test(string(v, 128)) ? (v as string) : fail();
const source = (v: unknown) =>
  v === "execution" || v === "fixture" ? v : fail();
const count = (v: unknown): number =>
  Number.isSafeInteger(v) && (v as number) >= 0 ? (v as number) : fail();
const status = (v: unknown) =>
  statuses.includes(v as RunStatus) ? (v as RunStatus) : fail();
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : fail());
const optional = (v: unknown) => v === undefined || v === null;
function verification(v: unknown) {
  if (optional(v)) return null;
  const o = object(v);
  for (const suite of ["security", "functional", "adversarial"]) {
    if (count(o[`${suite}_passed`]) > count(o[`${suite}_total`])) fail();
  }
  return o as unknown as NonNullable<RunResponse["verification"]>;
}
function event(v: unknown): SecurityEvent {
  const o = object(v);
  id(o.event_id);
  id(o.run_id);
  source(o.source);
  status(o.stage);
  string(o.message, 2000);
  if (
    !eventTypes.includes(String(o.event_type)) ||
    !["info", "warning", "error", "critical"].includes(String(o.severity))
  )
    fail();
  const timestamp = string(o.timestamp);
  if (
    !/(Z|[+-]\d{2}:\d{2})$/.test(timestamp) ||
    !Number.isFinite(Date.parse(timestamp))
  )
    fail();
  object(o.metadata ?? {});
  return { ...o, metadata: o.metadata ?? {} } as unknown as SecurityEvent;
}
export function healthPayload(v: unknown): HealthResponse {
  const o = object(v);
  return o.status === "ok" && o.service === "proofloop"
    ? { status: "ok", service: "proofloop" }
    : fail();
}
export function runPayload(v: unknown): RunResponse {
  const o = object(v);
  id(o.run_id);
  source(o.source);
  status(o.status);
  string(o.target, 128);
  const events = list(o.events ?? []).map(event);
  if (events.some((e) => e.run_id !== o.run_id || e.source !== o.source))
    fail();
  if (!optional(o.finding)) {
    const f = object(o.finding);
    id(f.id);
    string(f.title, 300);
    if (
      !["info", "low", "medium", "high", "critical"].includes(
        String(f.severity),
      )
    )
      fail();
  }
  if (!optional(o.baseline)) {
    const b = object(o.baseline);
    if (typeof b.reproduced !== "boolean") fail();
    if (
      !optional(b.observed_status) &&
      (count(b.observed_status) < 100 || count(b.observed_status) > 599)
    )
      fail();
  }
  if (!optional(o.patch)) {
    const p = object(o.patch);
    if (count(p.attempt) < 1 || count(p.attempt) > 10) fail();
    string(p.diff, 200000);
  }
  return {
    ...o,
    events,
    verification: verification(o.verification),
  } as unknown as RunResponse;
}
export function eventsPayload(v: unknown): EventsResponse {
  const o = object(v);
  id(o.run_id);
  source(o.source);
  const events = list(o.events).map(event);
  if (events.some((e) => e.run_id !== o.run_id || e.source !== o.source))
    fail();
  if (!optional(o.next_cursor)) string(o.next_cursor);
  return { ...o, events } as unknown as EventsResponse;
}
export function reportPayload(v: unknown): ReportResponse {
  const o = object(v);
  id(o.run_id);
  source(o.source);
  status(o.status);
  string(o.summary);
  for (const value of list(o.evidence ?? [])) {
    const e = object(value);
    id(e.artifact_id);
    string(e.description, 500);
    if (!/^[a-f0-9]{64}$/.test(String(e.sha256))) fail();
  }
  list(o.limitations).forEach((v) => string(v));
  return {
    ...o,
    evidence: o.evidence ?? [],
    verification: verification(o.verification),
  } as unknown as ReportResponse;
}
export function challengePayload(v: unknown): ChallengeResponse {
  const o = object(v);
  id(o.run_id);
  return o.source === "execution" && o.status === "challenging"
    ? (o as unknown as ChallengeResponse)
    : fail();
}
export function analyticsPayload(v: unknown): AnalyticsResponse {
  const o = object(v);
  source(o.source);
  if (count(o.verified_count) + count(o.rejected_count) > count(o.run_count))
    fail();
  for (const value of list(o.failure_patterns)) {
    const p = object(value);
    string(p.challenge_family);
    if (count(p.failures) > count(p.executions)) fail();
  }
  return o as unknown as AnalyticsResponse;
}

export function briefingPayload(v: unknown): import('../types').BriefingResponse {
  const o = object(v);
  id(o.run_id);
  if (o.source !== 'execution' || !['unavailable', 'not_generated', 'generating', 'ready', 'error'].includes(String(o.status))) fail();
  if (!/^[a-f0-9]{64}$/.test(String(o.report_sha256))) fail();
  if (o.status === 'ready') {
    if (!/^briefing_[a-f0-9]{64}$/.test(String(o.artifact_id))) fail();
    if (o.audio_path !== `/api/audio/${o.artifact_id}`) fail();
    string(o.transcript, 10000);
  }
  return o as unknown as import('../types').BriefingResponse;
}
