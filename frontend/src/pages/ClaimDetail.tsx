import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ChevronLeft, ChevronRight, Play, Pause } from "lucide-react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/plugins/regions";
import { api, type KeyClaim, type Transcript } from "../lib/api";
import { formatTimestamp } from "../lib/format";
import { VerdictBadge } from "../components/VerdictBadge";

const WINDOW_BEFORE = 2; // seconds of context before the cited quote
const WINDOW_AFTER = 8; // seconds of context after, since quotes run a few seconds long

export function ClaimDetail() {
  const { ticker = "", quarter = "", index = "0" } = useParams();
  const navigate = useNavigate();
  const idx = Number(index);

  const [claims, setClaims] = useState<KeyClaim[] | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [playing, setPlaying] = useState(false);

  const waveformRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);

  useEffect(() => {
    api.getClaims(ticker, quarter).then((d) => setClaims(d.claims));
    api.getTranscript(ticker, quarter).then(setTranscript);
  }, [ticker, quarter]);

  const claim = claims?.[idx];

  useEffect(() => {
    if (!claim || !waveformRef.current) return;

    wsRef.current?.destroy();
    const ws = WaveSurfer.create({
      container: waveformRef.current,
      waveColor: "#2a3029",
      progressColor: "#3ecf8e",
      cursorColor: "#f2f5f2",
      height: 64,
      url: api.audioUrl(ticker, quarter),
    });
    const regions = ws.registerPlugin(RegionsPlugin.create());

    const start = Math.max(0, claim.timestamp_sec - WINDOW_BEFORE);
    const end = claim.timestamp_sec + WINDOW_AFTER;

    ws.on("ready", () => {
      ws.zoom(40);
      regions.addRegion({ start, end, color: "rgba(62,207,142,0.15)", drag: false, resize: false });
      ws.setTime(start);
      ws.setScrollTime?.(Math.max(0, start - 3));
    });
    ws.on("play", () => setPlaying(true));
    ws.on("pause", () => setPlaying(false));
    ws.on("finish", () => setPlaying(false));

    wsRef.current = ws;
    return () => ws.destroy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [claim?.timestamp_sec, ticker, quarter]);

  if (!claims || !claim) {
    return <div className="px-10 py-10 text-sm text-text-faint">Loading…</div>;
  }

  const total = claims.length;
  const goTo = (next: number) => {
    if (next >= 0 && next < total) navigate(`/app/calls/${ticker}/${quarter}/claims/${next}`);
  };

  const contextBefore = transcript?.segments.filter((s) => s.start < claim.timestamp_sec).slice(-1)[0];
  const contextAfter = transcript?.segments.find((s) => s.start > claim.timestamp_sec);

  return (
    <div className="mx-auto max-w-3xl px-10 py-10">
      <div className="flex items-center justify-between">
        <Link
          to={`/app/calls/${ticker}/${quarter}`}
          className="flex items-center gap-2 text-sm text-text-muted hover:text-text"
        >
          <ArrowLeft size={14} /> Back to report
        </Link>
        <div className="flex items-center gap-3 text-sm text-text-muted">
          <button
            disabled={idx === 0}
            onClick={() => goTo(idx - 1)}
            className="rounded-full border border-border p-1.5 disabled:opacity-30"
          >
            <ChevronLeft size={14} />
          </button>
          Claim {idx + 1} of {total}
          <button
            disabled={idx === total - 1}
            onClick={() => goTo(idx + 1)}
            className="rounded-full border border-border p-1.5 disabled:opacity-30"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      <div className="mt-8 flex items-start justify-between gap-4">
        <blockquote className="text-xl font-medium leading-snug text-text">
          “{claim.claim}”
        </blockquote>
        <VerdictBadge verdict={claim.verdict} />
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-raised px-4 py-3">
          <div className="text-xs uppercase tracking-wide text-text-faint">Timestamp</div>
          <div className="mt-1 text-sm text-text">
            {claim.timestamp_sec}s ({formatTimestamp(claim.timestamp_sec)})
          </div>
        </div>
        <div className="rounded-lg border border-border bg-raised px-4 py-3">
          <div className="text-xs uppercase tracking-wide text-text-faint">Source text</div>
          <div className="mt-1 text-sm text-text">"{claim.evidence}"</div>
        </div>
      </div>

      <div className="mt-8">
        <div className="mb-2 flex items-center justify-between text-xs uppercase tracking-wide text-text-faint">
          Evidence from transcript
          <button
            onClick={() => wsRef.current?.playPause()}
            className="flex items-center gap-1.5 rounded-full bg-mint px-3 py-1 text-xs font-medium text-[#06120c]"
          >
            {playing ? <Pause size={12} /> : <Play size={12} />} {playing ? "Pause" : "Play"}
          </button>
        </div>
        <div ref={waveformRef} className="overflow-hidden rounded-lg border border-border bg-raised p-3" />
      </div>

      {(contextBefore || contextAfter) && (
        <div className="mt-8">
          <div className="mb-2 text-xs uppercase tracking-wide text-text-faint">Context</div>
          <div className="flex flex-col gap-2 text-xs text-text-faint">
            {contextBefore && (
              <div>
                <span className="text-text-muted">{formatTimestamp(contextBefore.start)}</span> …{contextBefore.text}
              </div>
            )}
            {contextAfter && (
              <div>
                <span className="text-text-muted">{formatTimestamp(contextAfter.start)}</span> {contextAfter.text}…
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
