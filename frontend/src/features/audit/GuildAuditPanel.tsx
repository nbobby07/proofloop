export type GuildReview = {
  sessionId: string;
  url: string;
  summary: string;
  evidenceDigest: string;
};
export function GuildAuditPanel({ review }: { review?: GuildReview }) {
  const safeUrl = review && /^https:\/\/app\.guild\.ai\//.test(review.url);
  return (
    <section className="panel sponsor-card">
      <p className="eyebrow">Guild · hosted evidence auditor</p>
      <h2>Evidence audit</h2>
      {review ? (
        <>
          <p>{review.summary}</p>
          {safeUrl && (
            <a
              className="text-link"
              href={review.url}
              target="_blank"
              rel="noreferrer"
            >
              Open hosted execution ↗
            </a>
          )}
          <p className="fine-print">
            Session {review.sessionId} · advisory review
          </p>
          <code>{review.evidenceDigest}</code>
        </>
      ) : (
        <>
          <p className="support">
            Reviews supported claims, missing evidence, and remaining
            limitations.
          </p>
          <span className="badge">Not connected</span>
          <p className="fine-print">
            An agent opinion cannot override deterministic verification.
          </p>
        </>
      )}
    </section>
  );
}
