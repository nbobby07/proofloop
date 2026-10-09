import { useEffect, useRef, useState } from "react";
import type { BriefingResponse, ReportResponse } from "../../types";
import {
  API_BASE_URL,
  errorMessage,
  generateBriefing,
  getBriefing,
} from "../../services/api";
import { Icon } from "../../components/Icon";
import { IncidentBriefingPlayer } from "./IncidentBriefingPlayer";

async function digestReport(report: ReportResponse): Promise<string> {
  const canonical = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(canonical);
    if (value !== null && typeof value === "object")
      return Object.fromEntries(
        Object.entries(value)
          .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
          .map(([key, item]) => [key, canonical(item)]),
      );
    return value;
  };
  const bytes = new TextEncoder().encode(JSON.stringify(canonical(report)));
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("");
}

export function BriefingPanel({ report }: { report: ReportResponse }) {
  const [result, setResult] = useState<BriefingResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const mutation = useRef<AbortController | null>(null);
  useEffect(() => () => mutation.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await getBriefing(report.run_id, controller.signal);
        const expected = await digestReport(report);
        if (!active) return;
        if (next.run_id !== report.run_id || next.report_sha256 !== expected)
          throw new Error(
            "The saved report changed. Refresh the run before generating narration.",
          );
        setResult(next);
        setError(null);
        if (next.status === "generating") timer = setTimeout(poll, 1200);
      } catch (reason) {
        if (active) setError(errorMessage(reason));
      }
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [report, revision]);
  const generate = async () => {
    if (busy || !result) return;
    const controller = new AbortController();
    mutation.current = controller;
    setBusy(true);
    setError(null);
    try {
      const next = await generateBriefing(
        report.run_id,
        result.report_sha256,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      if (
        next.run_id !== report.run_id ||
        next.report_sha256 !== result.report_sha256
      )
        throw new Error("Briefing identity mismatch.");
      setResult(next);
      setRevision((v) => v + 1);
    } catch (reason) {
      if (!controller.signal.aborted) setError(errorMessage(reason));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  if (result?.status === "ready" && !error)
    return (
      <IncidentBriefingPlayer
        audio={{
          runId: result.run_id,
          url: `${API_BASE_URL}${result.audio_path}`,
          transcript: result.transcript!,
          evidenceDigest: result.report_sha256,
        }}
      />
    );
  return (
    <section className="panel sponsor-card briefing-card">
      <div className="briefing-heading">
        <Icon name="volume" size={24} />
        <div>
          <p className="eyebrow">ELEVENLABS / REPORT NARRATION</p>
          <h2>Incident briefing</h2>
        </div>
      </div>
      <p className="fine-print">
        A short spoken summary of the result, key counts and next step. Full
        limitations remain in the written report.
      </p>
      <button
        disabled={
          busy ||
          !!error ||
          !result ||
          result.status === "unavailable" ||
          result.status === "generating"
        }
        onClick={() => void generate()}
      >
        {busy || result?.status === "generating"
          ? "Generating briefing…"
          : "Generate incident briefing"}
      </button>
      {result?.status === "unavailable" && (
        <p className="fine-print">
          Narration is not configured. Security evidence remains available.
        </p>
      )}
      {result?.status === "error" && (
        <p role="alert">
          Narration failed. The security verdict is unchanged. You can retry
          explicitly.
        </p>
      )}
      {error && (
        <>
          <p role="alert">{error}</p>
          <button
            onClick={() => {
              setError(null);
              setRevision((v) => v + 1);
            }}
          >
            Refresh briefing status
          </button>
        </>
      )}
    </section>
  );
}
