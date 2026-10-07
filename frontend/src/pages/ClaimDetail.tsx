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
  const [audioReady, setAudioReady] = useState(false);
  const [audioError, setAudioError] = useState(false);

  const waveformRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<InstanceType<typeof RegionsPlugin> | null>(null);

  useEffect(() => {
    api.getClaims(ticker, quarter).then((d) => setClaims(d.claims));
    api.getTranscript(ticker, quarter).then(setTranscript);
  }, [ticker, quarter]);

  const claim = claims?.[idx];

  // Load the audio ONCE per call — not per claim. Recreating WaveSurfer on every claim change
  // meant re-downloading and re-decoding the whole file each time, which is why the waveform
  // often looked empty: it just hadn't finished decoding yet.
  useEffect(() => {
    if (!waveformRef.current) return;
    setAudioReady(false);
    setAudioError(false);

    // Guard against React StrictMode's dev-mode double-invoke: the first instance can get
    // destroy()'d mid-load, and without this flag its late "ready" event would still fire and
    // wire up a dead WaveSurfer instance, leaving the waveform permanently blank.
    let cancelled = false;
    const ws = WaveSurfer.create({
      container: waveformRef.current,
      waveColor: "#2a3029",
      progressColor: "#3ecf8e",
      cursorColor: "#f2f5f2",
      height: 64,
      url: api.audioUrl(ticker, quarter),
    });
    const regions = ws.registerPlugin(RegionsPlugin.create());

    ws.on("ready", () => {
      if (cancelled) return;
      ws.zoom(40);
      regionsRef.current = regions;
      wsRef.current = ws;
      setAudioReady(true);
    });
    ws.on("play", () => !cancelled && setPlaying(true));
    ws.on("pause", () => !cancelled && setPlaying(false));
    ws.on("finish", () => !cancelled && setPlaying(false));
    // The source mp3 isn't in the repo (see README) -- on a fresh clone with only the
    // committed data/processed/ JSON, this fires instead of "ready". Fail visibly, not silently.
    ws.on("error", () => !cancelled && setAudioError(true));

    return () => {
      cancelled = true;
      ws.destroy();
      if (wsRef.current === ws) {
        wsRef.current = null;
        regionsRef.current = null;
      }
    };
    // `claims` loading is in the deps deliberately: until it resolves, the component renders a
    // "Loading…" placeholder instead of the waveform container, so `waveformRef.current` is null
    // on the first run of this effect. Re-running once `claims` flips from null to loaded is what
    // lets this retry after the real container has mounted. It does NOT depend on `idx`/`claim`,
    // so navigating between claims in the same call never re-triggers a reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker, quarter, !!claims]);

  // Moving between claims just repositions the highlighted region on the already-loaded audio.
  useEffect(() => {
    if (!audioReady || !claim || !wsRef.current || !regionsRef.current) return;
    regionsRef.current.clearRegions();
    const start = Math.max(0, claim.timestamp_sec - WINDOW_BEFORE);
    const end = claim.timestamp_sec + WINDOW_AFTER;
    regionsRef.current.addRegion({ start, end, color: "rgba(62,207,142,0.15)", drag: false, resize: false });
    wsRef.current.setTime(start);
  }, [audioReady, claim?.timestamp_sec]);

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
          {!audioError && (
            <button
              onClick={() => wsRef.current?.playPause()}
              disabled={!audioReady}
              className="flex items-center gap-1.5 rounded-full bg-mint px-3 py-1 text-xs font-medium text-[#06120c] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {playing ? <Pause size={12} /> : <Play size={12} />}{" "}
              {audioReady ? (playing ? "Pause" : "Play") : "Loading…"}
            </button>
          )}
        </div>
        <div className="relative overflow-hidden rounded-lg border border-border bg-raised p-3">
          {audioError ? (
            <div className="flex h-16 items-center justify-center text-xs text-text-faint">
              Audio unavailable — the source file isn't included in this checkout (see README).
            </div>
          ) : !audioReady ? (
            <div className="flex h-16 items-center justify-center text-xs text-text-faint">
              Decoding audio…
            </div>
          ) : null}
          <div ref={waveformRef} className={audioReady && !audioError ? "" : "hidden"} />
        </div>
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
