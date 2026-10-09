import { useEffect, useRef, useState } from "react";

export type BriefingAudio = {
  runId: string;
  url: string;
  transcript: string;
  evidenceDigest: string;
};
export function IncidentBriefingPlayer({ audio }: { audio?: BriefingAudio }) {
  const player = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(
    () => () => {
      player.current?.pause();
    },
    [audio?.url],
  );
  const play = async (replay = false) => {
    if (!player.current) return;
    try {
      if (replay) player.current.currentTime = 0;
      await player.current.play();
      setError(null);
    } catch {
      setError("Audio could not play. Retry or read the transcript.");
    }
  };
  return (
    <section className="panel sponsor-card">
      <p className="eyebrow">ElevenLabs · incident briefing</p>
      <h2>Incident briefing</h2>
      {audio ? (
        <>
          <audio
            ref={player}
            src={audio.url}
            preload="metadata"
            controls
            onLoadStart={() => setLoading(true)}
            onCanPlay={() => setLoading(false)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onError={() => {
              setLoading(false);
              setError("The saved audio is unavailable.");
            }}
          />
          <div className="button-row">
            <button
              disabled={loading}
              onClick={() => (playing ? player.current?.pause() : void play())}
            >
              {loading ? "Loading audio…" : playing ? "Pause" : "Play briefing"}
            </button>
            <button disabled={loading} onClick={() => void play(true)}>
              Replay ↻
            </button>
          </div>
          <details>
            <summary>Read transcript</summary>
            <p>{audio.transcript}</p>
            <code>{audio.evidenceDigest}</code>
          </details>
          {error && (
            <p role="alert" className="error-message">
              {error}
            </p>
          )}
        </>
      ) : (
        <>
          <p className="support">
            A spoken summary grounded in the completed run report.
          </p>
          <button disabled>Play incident briefing</button>
          <p className="fine-print">
            Open a completed live report to generate narration. Previous audio is
            unavailable while a fresh verification is running.
          </p>
        </>
      )}
    </section>
  );
}
