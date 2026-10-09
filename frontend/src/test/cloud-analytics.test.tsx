import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AnalyticsDashboard } from "../features/analytics/AnalyticsDashboard";
import { telemetryPayload } from "../services/validation";

const analytics = {
  source: "execution",
  run_count: 2,
  verified_count: 1,
  rejected_count: 1,
  failure_patterns: [],
};
const cloud = {
  source: "execution",
  storage: "clickhouse",
  analytics,
  event_count: 80,
  pending_events: 2,
  incomplete_rounds: 0,
  mean_patch_attempts: 1.5,
  mean_verification_duration_ms: 2400,
  latest_event_at: "2026-10-09T21:00:00Z",
  query_ms: 85,
};

it("labels SQL results and explicitly switches to local evidence on a cloud outage", async () => {
  let unavailable = false;
  let localUnavailable = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/telemetry/analytics"))
        return unavailable
          ? new Response("private provider failure", { status: 503 })
          : new Response(JSON.stringify(cloud));
      return localUnavailable
        ? new Response("offline", { status: 503 })
        : new Response(JSON.stringify(analytics));
    }),
  );
  render(<AnalyticsDashboard fixture={false} />);
  await screen.findByRole("heading", { name: "Live from ClickHouse" });
  expect(screen.getByText(/80 deduplicated events/)).toBeTruthy();
  expect(screen.getByText(/2 local events awaiting delivery/)).toBeTruthy();
  unavailable = true;
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: /Refresh analytics/ }));
  await screen.findByText(/Showing locally persisted analytics/);
  await waitFor(() =>
    expect(
      screen.queryByRole("heading", { name: "Live from ClickHouse" }),
    ).toBeNull(),
  );
  expect(screen.queryByText(/private provider failure/)).toBeNull();
  localUnavailable = true;
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: /Refresh analytics/ }));
  await screen.findByText(/Local analytics are loading or unavailable/);
  await waitFor(() =>
    expect(
      screen.getByText("Runs observed").parentElement?.querySelector("strong")
        ?.textContent,
    ).toBe("—"),
  );
});

it("does not query cloud or local analytics for fixture previews", () => {
  const network = vi.fn();
  vi.stubGlobal("fetch", network);
  render(<AnalyticsDashboard fixture />);
  expect(network).not.toHaveBeenCalled();
});

it("rejects fixture provenance and non-finite SQL metrics", () => {
  expect(() => telemetryPayload({ ...cloud, source: "fixture" })).toThrow();
  expect(() =>
    telemetryPayload({
      ...cloud,
      analytics: { ...analytics, source: "fixture" },
    }),
  ).toThrow();
  expect(() => telemetryPayload({ ...cloud, query_ms: Infinity })).toThrow();
  expect(() => telemetryPayload({ ...cloud, pending_events: -1 })).toThrow();
});
