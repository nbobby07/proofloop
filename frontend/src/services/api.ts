import type {
  AnalyticsResponse,
  ChallengeRequest,
  ChallengeResponse,
  CreateRunRequest,
  EventsResponse,
  HealthResponse,
  ReportResponse,
  RunResponse,
} from "../types";
import {
  analyticsPayload,
  briefingPayload,
  challengePayload,
  eventsPayload,
  healthPayload,
  reportPayload,
  runPayload,
} from "./validation";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  validate: (value: unknown) => T,
  signal?: AbortSignal,
  body?: unknown,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers:
        body === undefined
          ? { Accept: "application/json" }
          : { Accept: "application/json", "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal
        ? AbortSignal.any([signal, AbortSignal.timeout(12000)])
        : AbortSignal.timeout(12000),
      cache: "no-store",
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(
      0,
      "connection_error",
      "Cannot reach the backend. Check the server address and connection, then retry.",
    );
  }
  if (!response.ok) {
    const messages: Record<number, string> = {
      404: "This run could not be found.",
      409: "The run is not ready for this operation. Refresh its status and try again.",
      422: "The backend rejected the request parameters.",
      501: "This capability is planned. The backend has not implemented it yet.",
      503: "This service is temporarily unavailable.",
    };
    // Never reflect upstream tracebacks or provider secrets into the UI.
    throw new ApiError(
      response.status,
      `http_${response.status}`,
      messages[response.status] ||
        `The backend returned HTTP ${response.status}. Please retry.`,
    );
  }
  try {
    return validate(await response.json());
  } catch {
    throw new ApiError(
      response.status,
      "invalid_response",
      "The backend response does not match the frozen API contract. No result was accepted.",
    );
  }
}

const runPath = (id: string) => {
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(id))
    throw new ApiError(
      422,
      "invalid_request",
      "Enter a valid run ID (letters, numbers, underscores or hyphens).",
    );
  return `/api/runs/${encodeURIComponent(id)}`;
};
export const getHealth = (signal?: AbortSignal): Promise<HealthResponse> =>
  request("/api/health", healthPayload, signal);
export const createRun = (
  body: CreateRunRequest,
  signal?: AbortSignal,
): Promise<RunResponse> => request("/api/runs", runPayload, signal, body);
export const getRun = (
  id: string,
  signal?: AbortSignal,
): Promise<RunResponse> => request(runPath(id), runPayload, signal);
export const getRunEvents = (
  id: string,
  cursor?: string,
  signal?: AbortSignal,
): Promise<EventsResponse> => {
  const query = new URLSearchParams({ limit: "200" });
  if (cursor) query.set("cursor", cursor);
  return request(`${runPath(id)}/events?${query}`, eventsPayload, signal);
};
export const getReport = (
  id: string,
  signal?: AbortSignal,
): Promise<ReportResponse> =>
  request(`${runPath(id)}/report`, reportPayload, signal);
export const challengeRun = (
  id: string,
  body: ChallengeRequest,
  signal?: AbortSignal,
): Promise<ChallengeResponse> =>
  request(`${runPath(id)}/challenge`, challengePayload, signal, body);
export const getAnalytics = (
  signal?: AbortSignal,
  id?: string,
): Promise<AnalyticsResponse> =>
  request(
    `/api/analytics${id ? `?run_id=${encodeURIComponent(id)}` : ""}`,
    analyticsPayload,
    signal,
  );
export const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "The operation could not complete.";

export const getBriefing = (id: string, signal?: AbortSignal) =>
  request(`${runPath(id)}/briefing`, briefingPayload, signal);
export const generateBriefing = (id: string, digest: string, signal?: AbortSignal) =>
  request(`${runPath(id)}/briefing`, briefingPayload, signal, {report_sha256: digest});
