import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/plugins/regions";
import { api } from "../lib/api";
import { formatTimestamp } from "../lib/format";

export function EvidenceAudio({
  ticker,
  quarter,
  timestamp,
  end,
}: {
  ticker: string;
  quarter: string;
  timestamp: number;
  end: number;
}) {
  const container = useRef<HTMLDivElement>(null);
  const player = useRef<WaveSurfer | null>(null);
  const regions = useRef<InstanceType<typeof RegionsPlugin> | null>(null);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(false);
  const [playbackNotice, setPlaybackNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!container.current) return;
    let cancelled = false;
    const ws = WaveSurfer.create({
      container: container.current,
      waveColor: "#a99d86",
      progressColor: "#82662e",
      cursorColor: "#111113",
      height: 76,
      url: api.audioUrl(ticker, quarter),
      normalize: true,
    });
    const plugin = ws.registerPlugin(RegionsPlugin.create());
    player.current = ws;
    regions.current = plugin;
    ws.on("ready", () => {
      if (!cancelled) {
        ws.zoom(20);
        setReady(true);
      }
    });
    ws.on("play", () => {
      if (!cancelled) setPlaying(true);
    });
    ws.on("pause", () => {
      if (!cancelled) setPlaying(false);
    });
    ws.on("finish", () => {
      if (!cancelled) setPlaying(false);
    });
    ws.on("error", () => {
      if (!cancelled) setError(true);
    });
    return () => {
      cancelled = true;
      ws.destroy();
      player.current = null;
      regions.current = null;
    };
  }, [ticker, quarter]);

  useEffect(() => {
    if (!ready || !player.current || !regions.current) return;
    const duration = player.current.getDuration();
    const start = Math.max(0, Math.min(timestamp, duration));
    regions.current.clearRegions();
    regions.current.addRegion({
      start,
      end: Math.min(Math.max(end, start + 0.5), duration),
      color: "rgba(182,154,97,0.22)",
      drag: false,
      resize: false,
    });
    player.current.setTime(start);
  }, [ready, timestamp, end]);

  const play = () => {
    setPlaybackNotice(null);
    player.current
      ?.playPause()
      .catch(() =>
        setPlaybackNotice(
          "Playback could not start. Try the play control again.",
        ),
      );
  };
  return (
    <section className="waveform-panel" aria-label="Evidence audio player">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="eyebrow">Listen to the source</p>
          <button
            className="timestamp mt-1"
            disabled={!ready || error}
            onClick={() => {
              player.current?.setTime(timestamp);
              if (!playing) play();
            }}
          >
            <Play size={12} aria-hidden="true" />
            {formatTimestamp(timestamp)} / exact timestamp
          </button>
        </div>
        <button
          className="icon-btn"
          disabled={!ready || error}
          onClick={play}
          aria-label={playing ? "Pause evidence audio" : "Play evidence audio"}
        >
          {playing ? (
            <Pause size={16} aria-hidden="true" />
          ) : (
            <Play size={16} aria-hidden="true" />
          )}
        </button>
      </div>
      {!ready && !error && (
        <p className="waveform-status" role="status">
          Loading the source recording…
        </p>
      )}
      {error && (
        <p className="waveform-status" role="status">
          Audio is unavailable in this environment. The source quote and
          transcript remain available below.
        </p>
      )}
      {playbackNotice && (
        <p className="waveform-status" role="status">
          {playbackNotice}
        </p>
      )}
      <div
        ref={container}
        className="mt-4"
        style={{ display: error ? "none" : undefined }}
      />
      {ready && !error && (
        <p className="caption muted mt-3">
          The shaded passage marks the cited evidence. Scroll the waveform to
          explore the recording.
        </p>
      )}
    </section>
  );
}
