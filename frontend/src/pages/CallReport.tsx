import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Play } from "lucide-react";
import { api, type CallReport as CallReportT, type KeyClaim, type Transcript } from "../lib/api";
import { formatDate, formatTimestamp, formatPercent } from "../lib/format";
import { TickerBadge } from "../components/TickerBadge";
import { SentimentBar } from "../components/SentimentBar";
import { VerdictBadge } from "../components/VerdictBadge";

type Tab = "overview" | "claims" | "transcript";

export function CallReport() {
  const { ticker = "", quarter = "" } = useParams();
  const [tab, setTab] = useState<Tab>("overview");
  const [report, setReport] = useState<CallReportT | null>(null);
  const [claims, setClaims] = useState<KeyClaim[] | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [audioError, setAudioError] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    setReport(null);
    setClaims(null);
    setTranscript(null);
    setError(null);
    api.getCall(ticker, quarter).then(setReport).catch((e) => setError(e.message));
    api.getClaims(ticker, quarter).then((d) => setClaims(d.claims)).catch(() => {});
    api.getTranscript(ticker, quarter).then(setTranscript).catch(() => {});
  }, [ticker, quarter]);

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-10 py-10">
        <Link to="/app" className="flex items-center gap-2 text-sm text-text-muted hover:text-text">
          <ArrowLeft size={14} /> Back to dashboard
        </Link>
        <p className="mt-6 rounded-lg border border-negative/30 bg-negative/10 px-4 py-3 text-sm text-negative">
          {error}
        </p>
      </div>
    );
  }

  if (!report) {
    return <div className="px-10 py-10 text-sm text-text-faint">Loading…</div>;
  }

  const seekTo = (sec: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = sec;
      audioRef.current.play();
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-10 py-10">
      <Link to="/app" className="flex items-center gap-2 text-sm text-text-muted hover:text-text">
        <ArrowLeft size={14} /> Back to dashboard
      </Link>

      <div className="mt-6 flex items-center gap-4">
        <TickerBadge ticker={report.ticker} size={48} />
        <div>
          <h1 className="text-xl font-medium text-text">
            {report.company} {report.quarter} Earnings Call
          </h1>
          <p className="text-sm text-text-muted">{formatDate(report.call_date)}</p>
        </div>
      </div>

      <div className="mt-8 flex gap-1 border-b border-border">
        {(["overview", "claims", "transcript"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm capitalize transition-colors ${
              tab === t
                ? "border-mint text-mint"
                : "border-transparent text-text-muted hover:text-text"
            }`}
          >
            {t === "claims" ? `Claims (${claims?.length ?? report.key_claims.length})` : t}
          </button>
        ))}
      </div>

      {tab === "transcript" && (
        <>
          <audio
            ref={audioRef}
            src={api.audioUrl(ticker, quarter)}
            controls
            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
            onError={() => setAudioError(true)}
            className="sticky top-0 z-10 mt-4 h-10 w-full rounded-lg bg-raised"
          />
          {audioError && (
            <p className="mt-2 text-xs text-text-faint">
              Audio unavailable — the source file isn't included in this checkout (see README).
              Clicking a line below will have no effect.
            </p>
          )}
        </>
      )}

      {tab === "overview" && (
        <div className="mt-6 flex flex-col gap-6">
          <p className="text-sm leading-relaxed text-text-muted">{report.overall_summary}</p>

          <div className="grid grid-cols-3 gap-4">
            <Stat label="Citation accuracy" value={formatPercent(report.citation_verification.accuracy)} />
            <Stat
              label="Citations verified"
              value={`${report.citation_verification.verified}/${report.citation_verification.total_citations}`}
            />
            <Stat label="Claims extracted" value={String(report.key_claims.length)} />
          </div>

          <div>
            <div className="mb-2 text-xs uppercase tracking-wide text-text-faint">
              Sentiment distribution
            </div>
            <SentimentBar distribution={report.sentiment_distribution} />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <Stat
              label="Mean pitch"
              value={report.audio_features_summary.mean_pitch_hz ? `${report.audio_features_summary.mean_pitch_hz} Hz` : "N/A"}
            />
            <Stat
              label="Speaking rate"
              value={
                report.audio_features_summary.mean_speaking_rate_wps
                  ? `${report.audio_features_summary.mean_speaking_rate_wps} words/s`
                  : "N/A"
              }
            />
            <Stat label="Segments analyzed" value={String(report.audio_features_summary.segments_analyzed)} />
          </div>

          {report.prior_quarter_context_used.length > 0 && (
            <div>
              <div className="mb-2 text-xs uppercase tracking-wide text-text-faint">
                Cross-quarter context used (RAG)
              </div>
              <div className="flex flex-col gap-2">
                {report.prior_quarter_context_used.map((c, i) => (
                  <div key={i} className="rounded-lg border border-border bg-raised p-3 text-xs">
                    <span className="text-mint">{c.quarter}</span>
                    <p className="mt-1 text-text-muted">{c.text.slice(0, 200)}…</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "claims" && claims && (
        <div className="mt-6 flex flex-col gap-2">
          {claims.map((c, i) => (
            <Link
              key={i}
              to={`/app/calls/${ticker}/${quarter}/claims/${i}`}
              className="flex items-start justify-between gap-4 rounded-lg border border-border bg-raised p-4 transition-colors hover:border-mint/30"
            >
              <div>
                <p className="text-sm text-text">{c.claim}</p>
                <p className="mt-1 text-xs text-text-faint">{formatTimestamp(c.timestamp_sec)}</p>
              </div>
              <VerdictBadge verdict={c.verdict} />
            </Link>
          ))}
        </div>
      )}

      {tab === "transcript" && transcript && (
        <div className="mt-2 flex flex-col gap-1">
          {transcript.segments.map((seg, i) => {
            const next = transcript.segments[i + 1];
            const isActive = currentTime >= seg.start && (!next || currentTime < next.start) && currentTime > 0;
            return (
              <button
                key={i}
                onClick={() => seekTo(seg.start)}
                className={`group flex items-start gap-3 rounded-lg border-l-2 px-3 py-2 text-left transition-colors ${
                  isActive ? "border-mint bg-mint/5" : "border-transparent hover:bg-raised"
                }`}
              >
                <span className={`mt-0.5 flex items-center gap-1 text-xs ${isActive ? "text-mint" : "text-text-faint"}`}>
                  <Play size={10} className={isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"} />
                  {formatTimestamp(seg.start)}
                </span>
                <span className={`text-sm group-hover:text-text ${isActive ? "text-text" : "text-text-muted"}`}>
                  {seg.text}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-raised px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-text-faint">{label}</div>
      <div className="mt-1 text-lg font-medium text-text">{value}</div>
    </div>
  );
}
