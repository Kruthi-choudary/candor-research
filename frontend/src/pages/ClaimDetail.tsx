import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { formatTimestamp, formatPercent } from "../lib/format";
import { VerdictBadge } from "../components/VerdictBadge";
import { EmptyState } from "../components/States";
import { EvidenceAudio } from "../components/EvidenceAudio";
import { useCallData } from "../hooks/useCallData";
import {
  CallPreviewUnavailable,
  DataSourceNote,
} from "../components/DataStatus";

export function ClaimDetail() {
  const { ticker = "", quarter = "", index = "0" } = useParams();
  const navigate = useNavigate();
  const idx = Number(index);
  const { data, sources, reportResource, claimsAreLive } = useCallData(
    ticker,
    quarter,
  );
  const [previewSelected, setPreviewSelected] = useState(false);
  const reportUrl = `/app/calls/${ticker}/${quarter}`;
  if (!data)
    return (
      <CallPreviewUnavailable
        ticker={ticker}
        quarter={quarter}
        resource={reportResource}
      />
    );
  const { claims, transcript, report, claimsError, transcriptError } = data;
  if (claimsError)
    return (
      <div className="container page">
        <p className="notice">{claimsError}</p>
      </div>
    );
  const claim = Number.isInteger(idx) && idx >= 0 ? claims?.[idx] : undefined;
  if (!claim)
    return (
      <div className="container page">
        <Link className="back-link" to={reportUrl}>
          <ArrowLeft size={14} />
          Back to report
        </Link>
        <EmptyState
          title="This claim isn’t in the report."
          description="Return to the earnings brief to choose an available claim."
        />
      </div>
    );
  const segments = transcript?.segments ?? [];
  const sourceIndex = segments.reduce(
    (best, s, i) =>
      Math.abs(s.start - claim.timestamp_sec) <= 2 &&
      (best === -1 ||
        Math.abs(s.start - claim.timestamp_sec) <
          Math.abs(segments[best]!.start - claim.timestamp_sec))
        ? i
        : best,
    -1,
  );
  const excerpt =
    sourceIndex >= 0
      ? segments.slice(Math.max(0, sourceIndex - 1), sourceIndex + 3)
      : [];
  const source = segments[sourceIndex];

  return (
    <article className="container page reveal">
      <div className="evidence-head">
        <Link className="back-link" to={reportUrl}>
          <ArrowLeft size={14} aria-hidden="true" />
          Back to earnings brief
        </Link>
        <nav className="claim-pager tabular" aria-label="Claim navigation">
          <button
            className="icon-btn"
            aria-label="Previous claim"
            disabled={idx === 0}
            onClick={() => navigate(`${reportUrl}/claims/${idx - 1}`)}
          >
            <ChevronLeft size={16} aria-hidden="true" />
          </button>
          <span>
            Claim {idx + 1} of {claims?.length}
          </span>
          <button
            className="icon-btn"
            aria-label="Next claim"
            disabled={idx === (claims?.length ?? 0) - 1}
            onClick={() => navigate(`${reportUrl}/claims/${idx + 1}`)}
          >
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        </nav>
      </div>
      <DataSourceNote sources={sources} />
      <header className="rule-top">
        <p className="eyebrow muted">
          {report.company} / {report.quarter} / Evidence notebook
        </p>
        <h1 className="evidence-title">{claim.claim}</h1>
        <div className="report-meta">
          <VerdictBadge verdict={claim.verdict} />
          <span className="capitalize">{claim.sentiment} language</span>
          <span className="tabular">
            Source at {formatTimestamp(claim.timestamp_sec)}
          </span>
        </div>
      </header>
      <div className="evidence-layout">
        <div>
          <p className="eyebrow muted">01 / The supporting evidence</p>
          <blockquote className="evidence-quote">“{claim.evidence}”</blockquote>
          <p className="caption muted">
            Quoted from the automatic transcript. Read the surrounding passage
            before drawing a conclusion.
          </p>
          {claimsAreLive ? (
            <EvidenceAudio
              ticker={ticker}
              quarter={quarter}
              timestamp={claim.timestamp_sec}
              end={source?.end ?? claim.timestamp_sec + 8}
            />
          ) : (
            <section
              className="waveform-panel"
              aria-label="Demo transcript preview"
            >
              <p className="eyebrow">Explore the source passage</p>
              <p className="caption muted mt-3">
                No audio is bundled with this demo. Read the cited words and
                surrounding transcript without simulated playback.
              </p>
              <button
                className="timestamp mt-3"
                onClick={() => {
                  setPreviewSelected(true);
                  document
                    .getElementById("evidence-transcript")
                    ?.scrollIntoView?.({ block: "center" });
                }}
              >
                View transcript at {formatTimestamp(claim.timestamp_sec)}
              </button>
              {previewSelected && (
                <p className="caption muted" role="status">
                  Transcript preview selected at{" "}
                  {formatTimestamp(claim.timestamp_sec)}. No audio is playing.
                </p>
              )}
            </section>
          )}
          <section className="evidence-context" id="evidence-transcript">
            <div className="section-top">
              <h2 className="section-heading">The surrounding words</h2>
              <Link
                className="claim-action-link"
                to={`${reportUrl}?t=${claim.timestamp_sec}`}
              >
                Open report <ArrowUpRight size={14} aria-hidden="true" />
              </Link>
            </div>
            {transcriptError ? (
              <p className="notice" role="alert">
                {transcriptError}
              </p>
            ) : excerpt.length ? (
              excerpt.map((s, i) => (
                <div
                  className={`context-line ${s === source ? "current" : ""}`}
                  key={i}
                >
                  <Link
                    className="timestamp mr-3"
                    to={`${reportUrl}?t=${s.start}`}
                    aria-label={`Open source at ${formatTimestamp(s.start)}`}
                  >
                    {formatTimestamp(s.start)}
                  </Link>
                  <span>{s.text}</span>
                </div>
              ))
            ) : (
              <p className="notice">
                No transcript passage was found near this timestamp. Inspect the
                citation verdict and full report before relying on it.
              </p>
            )}
            <p className="caption muted mt-4">
              Speakers are not identified in the current transcript.
            </p>
          </section>
        </div>
        <aside className="report-aside">
          <p className="eyebrow muted mb-4">02 / The source check</p>
          <h2 className="section-heading">What was checked?</h2>
          <dl className="fact-list mt-4">
            <div>
              <dt>Citation status</dt>
              <dd>
                {claim.verdict === "VERIFIED"
                  ? "Matched"
                  : claim.verdict === "TEXT_MISMATCH"
                    ? "Text mismatch"
                    : claim.verdict === "TIMESTAMP_NOT_FOUND"
                      ? "Time not found"
                      : "Not checked"}
              </dd>
            </div>
            <div>
              <dt>Text similarity</dt>
              <dd>{formatPercent(claim.match_ratio)}</dd>
            </div>
            <div>
              <dt>Timestamp</dt>
              <dd>{formatTimestamp(claim.timestamp_sec)}</dd>
            </div>
            <div>
              <dt>Meaning reviewed</dt>
              <dd>Not established</dd>
            </div>
          </dl>
          <div className="notice mt-6">
            <strong>A source match is a starting point.</strong>
            <p>
              The checker compares quote text near the cited time. It does not
              determine whether the quote fully supports the claim, or whether
              the transcript is error-free.
            </p>
          </div>
          <Link className="text-link mt-5" to="/app/evaluation">
            Read the evaluation <ArrowUpRight size={14} aria-hidden="true" />
          </Link>
        </aside>
      </div>
    </article>
  );
}
