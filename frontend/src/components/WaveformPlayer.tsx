import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AudioError, decodeAudio, getAudioContext, type DecodedAudio } from "../audio/decode.ts";
import { BufferPlayer } from "../audio/player.ts";
import { computePeaks, timeToX, xToTime } from "../audio/waveform.ts";
import { formatTime } from "../lib/music.ts";

interface Props {
  /** A Blob (recording, upload, fixture) or a URL such as /api/audio/<id>. null means no audio. */
  source: Blob | string | null;
  label: string;
  /** Called about 60 times a second while playing, and on seek. */
  onPosition?: (seconds: number) => void;
}

type Status = "missing" | "loading" | "ready" | "error";

const HEIGHT = 128;

function cssVar(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export default function WaveformPlayer({ source, label, onPosition }: Props) {
  const [status, setStatus] = useState<Status>(source ? "loading" : "missing");
  const [message, setMessage] = useState("");
  const [decoded, setDecoded] = useState<DecodedAudio | null>(null);
  const [width, setWidth] = useState(600);
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);

  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const player = useRef<BufferPlayer | null>(null);
  const raf = useRef(0);
  const onPositionRef = useRef(onPosition);
  onPositionRef.current = onPosition;

  const report = useCallback((t: number) => {
    setPosition(t);
    onPositionRef.current?.(t);
  }, []);

  // Decode whenever the source changes.
  useEffect(() => {
    let cancelled = false;
    player.current?.dispose();
    player.current = null;
    setPlaying(false);
    setDecoded(null);
    report(0);
    if (!source) {
      setStatus("missing");
      setMessage("No audio to show.");
      return;
    }
    setStatus("loading");
    decodeAudio(source)
      .then((d) => {
        if (cancelled) return;
        const p = new BufferPlayer(getAudioContext(), d.buffer);
        p.onEnded = () => {
          setPlaying(false);
          report(p.duration);
        };
        player.current = p;
        setDecoded(d);
        setStatus("ready");
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setStatus("error");
        setMessage(e instanceof AudioError ? e.message : "The audio could not be shown.");
      });
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf.current);
      player.current?.dispose();
      player.current = null;
    };
  }, [source, report]);

  // Follow the container width.
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(120, Math.floor(entry.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Playhead loop.
  useEffect(() => {
    if (!playing) return;
    const loop = () => {
      const p = player.current;
      if (p) report(p.position);
      raf.current = requestAnimationFrame(loop);
    };
    raf.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, report]);

  const peaks = useMemo(() => (decoded ? computePeaks(decoded.mono, width) : []), [decoded, width]);
  const duration = decoded?.duration ?? 0;

  // Draw.
  useEffect(() => {
    const c = canvas.current;
    if (!c || status !== "ready") return;
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.floor(width * dpr);
    c.height = Math.floor(HEIGHT * dpr);
    const g = c.getContext("2d");
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, width, HEIGHT);
    const mid = HEIGHT / 2;
    const accent = cssVar("--color-accent", "#0e6b6b");
    const line = cssVar("--color-line", "#c9d0d7");
    const ink = cssVar("--color-ink", "#18212b");
    g.fillStyle = line;
    g.fillRect(0, mid, width, 1);
    const x = timeToX(position, duration, width);
    peaks.forEach((p, i) => {
      g.fillStyle = i <= x ? accent : line;
      const top = mid - p.max * (mid - 4);
      const bottom = mid - p.min * (mid - 4);
      g.fillRect(i, top, 1, Math.max(1, bottom - top));
    });
    g.fillStyle = ink;
    g.fillRect(Math.min(width - 2, x), 0, 2, HEIGHT);
  }, [peaks, position, width, duration, status]);

  const toggle = async () => {
    const p = player.current;
    if (!p) return;
    if (p.playing) {
      p.pause();
      setPlaying(false);
    } else {
      await p.play();
      setPlaying(true);
    }
  };

  const seek = (t: number) => {
    player.current?.seek(t);
    report(player.current?.position ?? 0);
  };

  const onPointer = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    seek(xToTime(e.clientX - rect.left, duration, rect.width));
  };

  const onKey = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      void toggle();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      seek(position + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      seek(position - 1);
    }
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-4">
        <h3 className="text-sm font-medium text-muted">{label}</h3>
        <span className="text-sm tabular-nums text-muted" aria-live="off">
          {status === "ready" ? `${formatTime(position)} / ${formatTime(duration)}` : ""}
        </span>
      </div>

      <div ref={wrap} className="w-full">
        {status === "ready" ? (
          <div
            role="slider"
            tabIndex={0}
            aria-label={`${label}: playback position`}
            aria-valuemin={0}
            aria-valuemax={Math.round(duration * 10) / 10}
            aria-valuenow={Math.round(position * 10) / 10}
            aria-valuetext={`${formatTime(position)} of ${formatTime(duration)}`}
            onClick={onPointer}
            onKeyDown={onKey}
            className="cursor-pointer rounded-sm border border-line bg-surface"
          >
            <canvas ref={canvas} style={{ width, height: HEIGHT, display: "block" }} />
          </div>
        ) : (
          <div
            role={status === "error" ? "alert" : "status"}
            className="flex items-center justify-center rounded-sm border border-dashed border-line bg-surface px-4 text-sm text-muted"
            style={{ height: HEIGHT }}
          >
            {status === "loading" ? "Reading audio..." : message}
          </div>
        )}
      </div>

      <div className="mt-2 flex items-center gap-3">
        <button
          type="button"
          onClick={() => void toggle()}
          disabled={status !== "ready"}
          className="rounded-sm bg-accent px-4 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {playing ? "Pause" : "Play"}
        </button>
        <span className="text-xs text-muted">Click the waveform or use the arrow keys to move the playhead.</span>
      </div>
    </div>
  );
}
