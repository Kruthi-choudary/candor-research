import { useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowUpRight, AudioLines, Play } from "lucide-react";
import { api } from "../lib/api";
import { formatDate, formatTimestamp, formatPercent } from "../lib/format";
import { SentimentBar } from "../components/SentimentBar";
import { VerdictBadge } from "../components/VerdictBadge";
import { EmptyState } from "../components/States";
import {
  CallPreviewUnavailable,
  DataSourceNote,
} from "../components/DataStatus";
import { ReportTabs, type ReportTab } from "../components/ReportTabs";
import { useCallData } from "../hooks/useCallData";

export function CallReport() {
  const { ticker = "", quarter = "" } = useParams();
  const [params] = useSearchParams();
  const initialTime = Number(params.get("t") ?? 0);
  const [tab, setTab] = useState<ReportTab>("overview");
  const { data, sources, reportResource, reportIsLive, transcriptIsLive } =
    useCallData(ticker, quarter);
  const [currentTime, setCurrentTime] = useState(
    Number.isFinite(initialTime) && initialTime >= 0 ? initialTime : 0,
  );
  const [audioError, setAudioError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const requestedTime = useRef(
    Number.isFinite(initialTime) && initialTime >= 0 ? initialTime : 0,
  );

  const seekTo = (sec: number) => {
    requestedTime.current = sec;
    setCurrentTime(sec);
    if (!reportIsLive) {
      setTab("transcript");
      return;
    }
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
  if (!data)
    return (
      <CallPreviewUnavailable
        ticker={ticker}
        quarter={quarter}
        resource={reportResource}
      />
    );
  const { report, claims, transcript, claimsError, transcriptError } = data;
  const features = report.audio_features_summary;
  const selectedExcerpt =
    !reportIsLive && currentTime > 0
      ? transcript?.segments.find(
          (seg) =>
            Math.abs(seg.start - currentTime) <= 2 ||
            (currentTime >= seg.start && currentTime < seg.end),
        )
      : null;

  return (
    <article className="container page reveal">
      <Link to="/app" className="back-link">
        <ArrowLeft size={14} aria-hidden="true" />
        Back to research desk
      </Link>
      <DataSourceNote sources={sources} />
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
            {report.report_version && <span>Version {report.report_version}</span>}
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
      {report.report_version && (
        <div className="notice mb-6">
          <strong>Evidence review scope</strong>
          <p>
            AI-assisted review against the saved transcript; independent human
            review is pending. Citation matching does not verify a claim’s meaning.
            Scheduled call dates have linked company announcements; the recordings
            have not been independently matched to those announcements. No
            executive-specific historical communication baseline has been evaluated.
            {report.prior_quarter_context_used.length === 0 &&
              " This report uses current-call evidence only."}
          </p>
        </div>
      )}
      <div className="audio-dock" aria-label="Source recording player">
        <div className="audio-info">
          <p className="eyebrow">
            {reportIsLive ? "The original recording" : "Transcript preview"}
          </p>
          <p className="caption muted">
            {formatTimestamp(currentTime)} <span aria-hidden="true"> / </span>{" "}
            {transcript
              ? formatTimestamp(transcript.duration_sec)
              : "source audio"}
          </p>
        </div>
        {reportIsLive ? (
          <audio
            aria-label={`${report.company} ${report.quarter} earnings-call audio`}
            ref={audioRef}
            src={api.audioUrl(ticker, quarter)}
            controls
            preload="metadata"
            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
            onLoadedMetadata={(e) => {
              const audio = e.currentTarget;
              audio.currentTime = Math.min(
                requestedTime.current,
                audio.duration,
              );
            }}
            onError={() =>
              setAudioError(
                "The source recording is unavailable here. You can still inspect every claim and transcript passage.",
              )
            }
          />
        ) : (
          <p className="audio-status">
            No audio is bundled with the demo. Select a timestamp to preview its
            transcript passage; playback becomes available only when a source
            recording can be loaded from the live API.
            {selectedExcerpt && (
              <span className="block mt-2" role="status">
                Selected passage at {formatTimestamp(currentTime)}: “
                {selectedExcerpt.text}”
              </span>
            )}
          </p>
        )}
        {reportIsLive && audioError && (
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
                  These describe the whole recording, which can include several
                  speakers. They are not yet compared against an individual
                  executive’s historical baseline.
                </p>
              </div>
              {report.prior_quarter_context_used.length > 0 && (
                <div className="section-space">
                  <h3>Retrieved context</h3>
                  <p className="caption muted mb-4">
                    {report.report_version
                      ? "Earlier company passages provide business context; they do not establish an executive communication baseline."
                      : "Context saved with this report. Older reports can include later-quarter passages and have not yet been regenerated with the historical-retrieval fix."}
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
              <p className="notice">{claimsError}</p>
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
                      <span className="font-normal">
                        {reportIsLive ? "/ play source" : "/ view passage"}
                      </span>
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
              <span>
                {reportIsLive
                  ? "Select a timestamp to play that exact moment."
                  : "Select a timestamp to highlight its transcript passage. Audio is not bundled."}
              </span>
              <span>
                {transcriptIsLive
                  ? "Automatic transcription · speakers are not identified"
                  : "Bundled transcript excerpts · gaps between passages are omitted"}
              </span>
            </div>
            {transcriptError ? (
              <p className="notice">{transcriptError}</p>
            ) : !transcript ? (
              <p className="notice">
                The full transcript is connecting. Explore the claim evidence
                while the live service responds.
              </p>
            ) : transcript.segments.length === 0 ? (
              <EmptyState
                title="No transcript passages available."
                description="The source recording can still be played above when available."
              />
            ) : (
              transcript?.segments.map((seg, i) => (
                <div
                  className={`transcript-row ${(reportIsLive ? currentTime >= seg.start && currentTime < seg.end : seg === selectedExcerpt) && currentTime > 0 ? "is-active" : ""}`}
                  key={i}
                >
                  <button
                    className="timestamp"
                    onClick={() => seekTo(seg.start)}
                    aria-label={`${reportIsLive ? "Play transcript" : "Preview transcript"} at ${formatTimestamp(seg.start)}`}
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
