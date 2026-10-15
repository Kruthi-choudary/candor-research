import { useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowUpRight, AudioLines, Play } from "lucide-react";
import { api } from "../lib/api";
import { formatDate, formatTimestamp, formatPercent } from "../lib/format";
import { SentimentBar } from "../components/SentimentBar";
import { VerdictBadge } from "../components/VerdictBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { ReportTabs, type ReportTab } from "../components/ReportTabs";
import { useCallData } from "../hooks/useCallData";

export function CallReport() {
  const { ticker = "", quarter = "" } = useParams();
  const [params] = useSearchParams();
  const initialTime = Number(params.get("t") ?? 0);
  const [tab, setTab] = useState<ReportTab>("overview");
  const { data, error } = useCallData(ticker, quarter);
  const [currentTime, setCurrentTime] = useState(0);
  const [audioError, setAudioError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const requestedTime = useRef(
    Number.isFinite(initialTime) && initialTime >= 0 ? initialTime : 0,
  );

  const seekTo = (sec: number) => {
    requestedTime.current = sec;
    const audio = audioRef.current;
    if (audio && audio.readyState >= 1 && !audio.error) {
      audio.currentTime = Math.min(
        sec,
        Number.isFinite(audio.duration) ? audio.duration : sec,
      );
      setCurrentTime(audio.currentTime);
      audio.play().catch(() => {
        setAudioError(
          "Playback was paused by your browser. Press play in the audio controls to continue.",
        );
      });
    }
  };
  if (error)
    return (
      <div className="container page">
        <Link to="/app" className="back-link">
          <ArrowLeft size={14} />
          Research desk
        </Link>
        <ErrorState message={error} />
      </div>
    );
  if (!data)
    return (
      <div className="container page">
        <LoadingState label="Opening the earnings brief…" />
      </div>
    );
  const { report, claims, transcript, claimsError, transcriptError } = data;
  const features = report.audio_features_summary;

  return (
    <article className="container page reveal">
      <Link to="/app" className="back-link">
        <ArrowLeft size={14} aria-hidden="true" />
        Back to research desk
      </Link>
      <header className="report-header">
        <div>
          <p className="eyebrow muted">
            {report.ticker} / Earnings intelligence
          </p>
          <h1 className="page-title">
            {report.company} <span className="editorial">{report.quarter}</span>
          </h1>
          <div className="report-meta">
            <time dateTime={report.call_date ?? undefined}>
              {formatDate(report.call_date)}
            </time>
            <span>{report.key_claims.length} extracted claims</span>
            <span>
              {transcript
                ? `${Math.round(transcript.duration_sec / 60)} minute recording`
                : "Earnings-call analysis"}
            </span>
          </div>
        </div>
        <Link className="text-link" to="/app/evaluation">
          About the methodology <ArrowUpRight size={14} aria-hidden="true" />
        </Link>
      </header>
      <div className="audio-dock" aria-label="Source recording player">
        <div className="audio-info">
          <p className="eyebrow">The original recording</p>
          <p className="caption muted">
            {formatTimestamp(currentTime)} <span aria-hidden="true"> / </span>{" "}
            {transcript
              ? formatTimestamp(transcript.duration_sec)
              : "source audio"}
          </p>
        </div>
        <audio
          aria-label={`${report.company} ${report.quarter} earnings-call audio`}
          ref={audioRef}
          src={api.audioUrl(ticker, quarter)}
          controls
          preload="metadata"
          onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
          onLoadedMetadata={(e) => {
            const audio = e.currentTarget;
            audio.currentTime = Math.min(requestedTime.current, audio.duration);
          }}
          onError={() =>
            setAudioError(
              "The source recording is unavailable here. You can still inspect every claim and transcript passage.",
            )
          }
        />
        {audioError && (
          <p className="audio-status" role="status">
            {audioError}
          </p>
        )}
      </div>
      <ReportTabs
        selected={tab}
        onSelect={setTab}
        count={claims?.length ?? report.key_claims.length}
      />
      <section
        id="report-panel"
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
        tabIndex={0}
      >
        {tab === "overview" && (
          <div className="report-layout">
            <div>
              <p className="eyebrow muted">01 / The executive brief</p>
              <h2 className="section-heading mt-3">What the call revealed.</h2>
              <p className="report-summary">{report.overall_summary}</p>
              <div className="metric-row">
                <div className="metric">
                  <p className="metric-value">
                    {formatPercent(report.citation_verification.accuracy)}
                  </p>
                  <p className="metric-label">Citation-match rate</p>
                </div>
                <div className="metric">
                  <p className="metric-value">
                    {report.citation_verification.verified}/
                    {report.citation_verification.total_citations}
                  </p>
                  <p className="metric-label">Citations matched</p>
                </div>
                <div className="metric">
                  <p className="metric-value">
                    {report.key_claims.length.toString().padStart(2, "0")}
                  </p>
                  <p className="metric-label">Extracted claims</p>
                </div>
              </div>
              <p className="caption muted mt-4">
                Matches confirm quote text near a timestamp, not independent
                verification of a claim.
              </p>
              <div className="section-space">
                <div className="section-top">
                  <h2 className="section-heading">Inside the evidence</h2>
                  <button
                    className="text-link bg-transparent border-x-0 border-t-0"
                    onClick={() => setTab("claims")}
                  >
                    All claims <ArrowUpRight size={14} aria-hidden="true" />
                  </button>
                </div>
                {claimsError ? (
                  <p className="notice" role="alert">
                    {claimsError}
                  </p>
                ) : (
                  claims?.slice(0, 2).map((claim, i) => (
                    <div className="claim-row" key={i}>
                      <span className="claim-number">0{i + 1}</span>
                      <div>
                        <h3 className="claim-title">
                          <Link
                            to={`/app/calls/${ticker}/${quarter}/claims/${i}`}
                          >
                            {claim.claim}
                          </Link>
                        </h3>
                        <button
                          className="timestamp mt-2"
                          onClick={() => seekTo(claim.timestamp_sec)}
                        >
                          <Play size={12} aria-hidden="true" />
                          {formatTimestamp(claim.timestamp_sec)}
                        </button>
                      </div>
                      <div className="claim-actions">
                        <VerdictBadge verdict={claim.verdict} />
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
            <aside className="report-aside">
              <p className="eyebrow muted mb-3">Signals, in context</p>
              <h3>Transcript sentiment</h3>
              <SentimentBar distribution={report.sentiment_distribution} />
              <p className="caption muted mt-4">
                Share of transcript segments classified by FinBERT. This
                measures language tone, not investor sentiment.
              </p>
              <div className="section-space">
                <h3>Vocal patterns</h3>
                <dl className="fact-list">
                  <div>
                    <dt>Mean pitch</dt>
                    <dd>
                      {features.mean_pitch_hz != null
                        ? `${features.mean_pitch_hz} Hz`
                        : "Unavailable"}
                    </dd>
                  </div>
                  <div>
                    <dt>Speaking rate</dt>
                    <dd>
                      {features.mean_speaking_rate_wps != null
                        ? `${features.mean_speaking_rate_wps} words/s`
                        : "Unavailable"}
                    </dd>
                  </div>
                  <div>
                    <dt>Segments analysed</dt>
                    <dd>{features.segments_analyzed}</dd>
                  </div>
                </dl>
                <p className="caption muted mt-4">
                  Descriptive audio measurements. They are not a measure of
                  honesty or executive confidence.
                </p>
              </div>
              {report.prior_quarter_context_used.length > 0 && (
                <div className="section-space">
                  <h3>Retrieved context</h3>
                  <p className="caption muted mb-4">
                    Other calls surfaced by the current retrieval system;
                    chronological filtering is not guaranteed.
                  </p>
                  {report.prior_quarter_context_used.map((c, i) => (
                    <details key={i} className="border-t border-rule py-3">
                      <summary className="text-sm cursor-pointer">
                        {c.quarter}{" "}
                        <span className="caption muted">
                          / {formatTimestamp(c.start_sec)}
                        </span>
                      </summary>
                      <p className="caption muted mt-3">{c.text}</p>
                    </details>
                  ))}
                </div>
              )}
            </aside>
          </div>
        )}
        {tab === "claims" && (
          <>
            <div className="section-top">
              <div>
                <p className="eyebrow muted mb-2">02 / Claims & evidence</p>
                <h2 className="section-heading">
                  Every conclusion has a source.
                </h2>
              </div>
            </div>
            <p className="notice mb-5">
              A <strong>citation match</strong> means the quoted text matches
              the transcript near the cited timestamp. Open a claim to assess
              its interpretation against the surrounding passage.
            </p>
            {claimsError ? (
              <ErrorState message={claimsError} />
            ) : claims?.length === 0 ? (
              <EmptyState
                title="No claims in this report."
                description="The transcript remains available for direct inspection."
              />
            ) : (
              claims?.map((claim, i) => (
                <div className="claim-row" key={i}>
                  <span className="claim-number">
                    {(i + 1).toString().padStart(2, "0")}
                  </span>
                  <div>
                    <h3 className="claim-title">
                      <Link to={`/app/calls/${ticker}/${quarter}/claims/${i}`}>
                        {claim.claim}
                      </Link>
                    </h3>
                    <p className="claim-excerpt">“{claim.evidence}”</p>
                    <button
                      className="timestamp"
                      onClick={() => seekTo(claim.timestamp_sec)}
                    >
                      <Play size={12} aria-hidden="true" />
                      {formatTimestamp(claim.timestamp_sec)}
                      <span className="font-normal">/ play source</span>
                    </button>
                  </div>
                  <div className="claim-actions">
                    <VerdictBadge verdict={claim.verdict} />
                    <Link
                      className="claim-action-link"
                      to={`/app/calls/${ticker}/${quarter}/claims/${i}`}
                    >
                      Inspect evidence{" "}
                      <ArrowUpRight size={14} aria-hidden="true" />
                    </Link>
                  </div>
                </div>
              ))
            )}
          </>
        )}
        {tab === "transcript" && (
          <>
            <div className="section-top">
              <div>
                <p className="eyebrow muted mb-2">03 / The transcript</p>
                <h2 className="section-heading">In their own words.</h2>
              </div>
              <AudioLines size={22} strokeWidth={1.3} aria-hidden="true" />
            </div>
            <div className="transcript-note">
              <span>Select a timestamp to play that exact moment.</span>
              <span>Automatic transcription · speakers are not identified</span>
            </div>
            {transcriptError ? (
              <ErrorState message={transcriptError} />
            ) : transcript?.segments.length === 0 ? (
              <EmptyState
                title="No transcript passages available."
                description="The source recording can still be played above when available."
              />
            ) : (
              transcript?.segments.map((seg, i) => (
                <div
                  className={`transcript-row ${currentTime >= seg.start && currentTime < seg.end && currentTime > 0 ? "is-active" : ""}`}
                  key={i}
                >
                  <button
                    className="timestamp"
                    onClick={() => seekTo(seg.start)}
                    aria-label={`Play transcript at ${formatTimestamp(seg.start)}`}
                  >
                    <Play size={11} aria-hidden="true" />
                    {formatTimestamp(seg.start)}
                  </button>
                  <p>{seg.text}</p>
                </div>
              ))
            )}
          </>
        )}
      </section>
    </article>
  );
}
