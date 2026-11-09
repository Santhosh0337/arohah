import { useEffect, useMemo, useRef, useState } from "react";
import type { Note } from "../api/types.ts";
import { formatTime, isBlackKey, noteName } from "../lib/music.ts";
import {
  confidenceLabel,
  hitTest,
  layoutNotes,
  pitchRange,
  timeSpan,
  type RollView,
} from "../lib/pianoRollModel.ts";

interface Props {
  notesRaw: Note[];
  notesClean: Note[];
  durationS: number;
  /** Playback position in seconds, from the waveform */
  position: number;
  /** Says where the notes came from, shown under the roll */
  provenance: string;
}

const HEIGHT = 260;
const GUTTER = 44;
const AXIS = 18;

function cssVar(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

export default function PianoRoll({ notesRaw, notesClean, durationS, position, provenance }: Props) {
  const [view, setView] = useState<RollView>("clean");
  const [width, setWidth] = useState(600);
  const [hover, setHover] = useState(-1);
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);

  const notes = view === "raw" ? notesRaw : notesClean;
  // One range and span for both views, so toggling does not rescale the axes.
  const range = useMemo(() => pitchRange([...notesRaw, ...notesClean]), [notesRaw, notesClean]);
  const span = useMemo(() => timeSpan([...notesRaw, ...notesClean], durationS), [notesRaw, notesClean, durationS]);
  const plotW = Math.max(60, width - GUTTER);
  const plotH = HEIGHT - AXIS;
  const rects = useMemo(
    () => layoutNotes(notes, { width: plotW, height: plotH, range, span }),
    [notes, plotW, plotH, range, span],
  );

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(200, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.floor(width * dpr);
    c.height = Math.floor(HEIGHT * dpr);
    const g = c.getContext("2d");
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, width, HEIGHT);

    const accent = cssVar("--color-accent", "#0e6b6b");
    const line = cssVar("--color-line", "#c9d0d7");
    const muted = cssVar("--color-muted", "#566170");
    const ink = cssVar("--color-ink", "#18212b");
    const rows = range.high - range.low + 1;
    const rowH = plotH / rows;
    g.font = "11px system-ui, sans-serif";
    g.textBaseline = "middle";

    // Rows: shade black keys, label every C and the lowest row.
    for (let p = range.low; p <= range.high; p++) {
      const y = (range.high - p) * rowH;
      if (isBlackKey(p)) {
        g.fillStyle = "rgba(24,33,43,0.06)";
        g.fillRect(GUTTER, y, plotW, rowH);
      }
      const isC = p % 12 === 0;
      if (isC) {
        g.fillStyle = line;
        g.fillRect(GUTTER, y + rowH, plotW, 1);
      }
      // Label every white key when rows are tall enough, otherwise only C.
      if (isC || p === range.low || (rowH >= 13 && !isBlackKey(p))) {
        g.fillStyle = isC ? ink : muted;
        g.textAlign = "right";
        g.fillText(noteName(p), GUTTER - 6, y + rowH / 2);
      }
    }

    // Time grid
    g.textAlign = "center";
    g.textBaseline = "alphabetic";
    const step = span > 30 ? 10 : span > 12 ? 5 : span > 4 ? 2 : 1;
    for (let t = 0; t <= span + 1e-6; t += step) {
      const x = GUTTER + (t / span) * plotW;
      g.fillStyle = line;
      g.fillRect(x, 0, 1, plotH);
      g.fillStyle = muted;
      g.fillText(`${t}s`, Math.min(width - 10, Math.max(GUTTER, x)), HEIGHT - 4);
    }

    // Notes
    rects.forEach((r) => {
      const x = GUTTER + r.x;
      const lowConf = r.confidence !== null && r.confidence < 0.5;
      g.globalAlpha = r.alpha;
      g.fillStyle = r.confidence === null ? muted : accent;
      g.fillRect(x, r.y + 0.5, r.w, r.h);
      g.globalAlpha = 1;
      g.lineWidth = r.index === hover ? 2 : 1;
      g.strokeStyle = r.index === hover ? ink : r.confidence === null ? muted : accent;
      g.setLineDash(lowConf ? [3, 2] : []);
      g.strokeRect(x + 0.5, r.y + 1, Math.max(1, r.w - 1), Math.max(1, r.h - 1));
      g.setLineDash([]);
    });

    // Playhead
    if (position > 0) {
      const x = GUTTER + Math.min(plotW, (position / span) * plotW);
      g.fillStyle = ink;
      g.fillRect(x, 0, 2, plotH);
    }
  }, [width, rects, range, span, plotW, plotH, position, hover]);

  const onMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    setHover(hitTest(rects, e.clientX - box.left - GUTTER, e.clientY - box.top));
  };

  const hovered = hover >= 0 ? notes[hover] : undefined;
  const summary = `Piano roll, ${view === "raw" ? "raw" : "cleaned"} notes: ${notes.length} notes from ${noteName(range.low)} to ${noteName(range.high)}.`;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-muted">Melody ({notes.length} notes)</h3>
        <div role="radiogroup" aria-label="Which notes to show" className="inline-flex overflow-hidden rounded-sm border border-line">
          {(
            [
              ["raw", `Raw (${notesRaw.length})`],
              ["clean", `Cleaned (${notesClean.length})`],
            ] as const
          ).map(([value, text]) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={view === value}
              onClick={() => setView(value)}
              className={`px-3 py-1 text-sm ${view === value ? "bg-accent text-white" : "bg-surface text-ink"}`}
            >
              {text}
            </button>
          ))}
        </div>
      </div>

      <div ref={wrap} className="w-full rounded-sm border border-line bg-surface">
        <canvas
          ref={canvas}
          role="img"
          aria-label={summary}
          style={{ width, height: HEIGHT, display: "block" }}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(-1)}
        />
        {notes.length === 0 && (
          <p className="px-4 py-3 text-sm text-muted">No notes to show in this view.</p>
        )}
      </div>

      <p className="mt-2 min-h-5 text-sm" aria-live="polite">
        {hovered
          ? `${noteName(hovered.pitch)} (MIDI ${hovered.pitch}), ${formatTime(hovered.start)} to ${formatTime(hovered.end)}, velocity ${hovered.velocity}, confidence ${confidenceLabel(hovered.confidence)}`
          : <span className="text-muted">Hover a note for details.</span>}
      </p>
      <p className="text-xs text-muted">
        Opacity shows velocity. A dashed outline means confidence below 50%. Grey means confidence unknown.
      </p>
      <p className="mt-1 text-xs text-muted">{provenance}</p>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted">Note list</summary>
        <table className="mt-2 w-full text-left text-sm">
          <thead className="text-muted">
            <tr>
              <th className="pr-4 font-medium">Note</th>
              <th className="pr-4 font-medium">MIDI</th>
              <th className="pr-4 font-medium">Start</th>
              <th className="pr-4 font-medium">End</th>
              <th className="pr-4 font-medium">Velocity</th>
              <th className="font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {notes.map((n, i) => (
              <tr key={i}>
                <td className="pr-4">{noteName(n.pitch)}</td>
                <td className="pr-4">{n.pitch}</td>
                <td className="pr-4">{n.start.toFixed(2)} s</td>
                <td className="pr-4">{n.end.toFixed(2)} s</td>
                <td className="pr-4">{n.velocity}</td>
                <td>{confidenceLabel(n.confidence)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
