import { useCallback, useEffect, useRef, useState } from "react";
import type { ReportResponse, RunResponse, SecurityEvent } from "../../types";
import {
  ApiError,
  challengeRun,
  createRun,
  errorMessage,
  getReport,
  getRun,
  getRunEvents,
} from "../../services/api";
import { mergeEvents, terminal } from "./lifecycle";

export function useRun(enabled: boolean) {
  const [run, setRun] = useState<RunResponse | null>(null);
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [polling, setPolling] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [selection, setSelection] = useState({ id: "", revision: 0 });
  const [history, setHistory] = useState<RunResponse[]>([]);
  const mutation = useRef<AbortController | null>(null);
  const pendingChallenge = useRef<Set<string> | null>(null);
  const runId = selection.id;

  useEffect(() => () => mutation.current?.abort(), [enabled]);
  useEffect(() => {
    if (!enabled || !runId) return;
    const controller = new AbortController();
    let active = true,
      cursor: string | undefined,
      observedProgress = false;
    let accumulated: SecurityEvent[] = [];
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      setPolling(true);
      let keepPolling = true;
      try {
        const snapshot = await getRun(runId, controller.signal);
        if (!active) return;
        if (snapshot.run_id !== runId || snapshot.source !== "execution")
          throw new Error("Live mode rejected a mismatched or fixture run.");
        let backlog = false;
        for (let page = 0; page < 5; page++) {
          const response = await getRunEvents(runId, cursor, controller.signal);
          if (!active) return;
          if (response.run_id !== runId || response.source !== "execution")
            throw new Error("Live mode rejected mismatched or fixture events.");
          accumulated = mergeEvents(accumulated, response.events);
          const next = response.next_cursor ?? undefined;
          backlog = !!next && next !== cursor && response.events.length > 0;
          if (next) cursor = next;
          if (!backlog) break;
        }
        // Snapshot events can be ahead of an undrained paginated backlog.
        // Use stream delivery order rather than inserting those events early.
        const allEvents = accumulated;
        accumulated = allEvents;
        if (!terminal(snapshot.status)) observedProgress = true;
        const challengePending = pendingChallenge.current;
        const freshCompletion = allEvents.some(
          (e) =>
            (e.event_type === "run_completed" ||
              e.event_type === "run_failed") &&
            !challengePending?.has(e.event_id),
        );
        const awaitingChallenge =
          challengePending !== null && !observedProgress && !freshCompletion;
        if (!awaitingChallenge) pendingChallenge.current = null;
        const displayed: RunResponse = awaitingChallenge
          ? { ...snapshot, status: "challenging", verification: null }
          : snapshot;
        setRun(displayed);
        setEvents(allEvents);
        setError(null);
        setUpdatedAt(new Date());
        if (!terminal(displayed.status)) setReport(null);
        setHistory((previous) =>
          [
            displayed,
            ...previous.filter((r) => r.run_id !== displayed.run_id),
          ].slice(0, 30),
        );
        if (terminal(displayed.status) && !backlog) {
          try {
            const result = await getReport(runId, controller.signal);
            if (!active) return;
            if (
              result.source !== "execution" ||
              result.run_id !== runId ||
              result.status !== displayed.status
            )
              throw new Error(
                "Report identity or status does not match the current run.",
              );
            setReport(result);
            setReportError(null);
            keepPolling = false;
          } catch (reason) {
            if (!active) return;
            setReportError(errorMessage(reason));
            keepPolling = reason instanceof ApiError && reason.status === 409;
          }
        }
      } catch (reason) {
        if (!active) return;
        setError(errorMessage(reason));
        if (
          reason instanceof ApiError &&
          [404, 422, 501].includes(reason.status)
        )
          keepPolling = false;
      } finally {
        if (active) {
          setPolling(false);
          if (keepPolling) timer = setTimeout(poll, 1800);
        }
      }
    };
    void poll();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [enabled, runId, selection.revision]);

  const open = useCallback((id: string) => {
    mutation.current?.abort();
    pendingChallenge.current = null;
    setRun(null);
    setEvents([]);
    setReport(null);
    setError(null);
    setReportError(null);
    setUpdatedAt(null);
    setBusy(false);
    setSelection((previous) => ({
      id: id.trim(),
      revision: previous.revision + 1,
    }));
  }, []);
  const start = async () => {
    if (!enabled || busy) return;
    const controller = new AbortController();
    mutation.current?.abort();
    mutation.current = controller;
    setBusy(true);
    setError(null);
    try {
      const result = await createRun(
        { target: "LedgerLite", max_attempts: 3 },
        controller.signal,
      );
      if (controller.signal.aborted) return;
      if (result.source !== "execution")
        throw new Error("Live mode rejected a fixture response.");
      open(result.run_id);
      setRun(result);
    } catch (reason) {
      if (!controller.signal.aborted) setError(errorMessage(reason));
    } finally {
      if (mutation.current === controller) setBusy(false);
    }
  };
  const challenge = async () => {
    if (!enabled || busy || !run || !terminal(run.status)) return;
    const controller = new AbortController();
    mutation.current?.abort();
    mutation.current = controller;
    setBusy(true);
    setError(null);
    try {
      const result = await challengeRun(
        run.run_id,
        { max_challenges: 2, policy_ids: [] },
        controller.signal,
      );
      if (controller.signal.aborted) return;
      if (result.run_id !== run.run_id)
        throw new Error("Challenge response belongs to another run.");
      pendingChallenge.current = new Set(events.map((e) => e.event_id));
      setRun({ ...run, status: "challenging", verification: null });
      setReport(null);
      setReportError(null);
      setSelection((previous) => ({
        ...previous,
        revision: previous.revision + 1,
      }));
    } catch (reason) {
      if (!controller.signal.aborted) setError(errorMessage(reason));
    } finally {
      if (mutation.current === controller) setBusy(false);
    }
  };
  return {
    run,
    events,
    report,
    error,
    reportError,
    busy,
    polling,
    updatedAt,
    history,
    start,
    challenge,
    open,
    refresh: () =>
      setSelection((previous) => ({
        ...previous,
        revision: previous.revision + 1,
      })),
  };
}
