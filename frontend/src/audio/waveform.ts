// Waveform maths. Pure, so it can be tested without a browser.

export interface Peak {
  min: number;
  max: number;
}

/**
 * Reduces PCM samples to `buckets` min/max pairs for drawing.
 * Returns an empty array for no samples or no buckets, never throws.
 */
export function computePeaks(samples: ArrayLike<number>, buckets: number): Peak[] {
  const n = samples.length;
  const count = Math.floor(buckets);
  if (n === 0 || !(count > 0)) return [];
  const peaks: Peak[] = [];
  const size = n / count;
  for (let b = 0; b < count; b++) {
    const from = Math.floor(b * size);
    const to = Math.max(from + 1, Math.min(n, Math.floor((b + 1) * size)));
    let min = 0;
    let max = 0;
    for (let i = from; i < to; i++) {
      const v = samples[i];
      if (v < min) min = v;
      if (v > max) max = v;
    }
    peaks.push({ min, max });
  }
  return peaks;
}

/** Mixes channels down to mono for display. */
export function mixToMono(channels: ArrayLike<number>[]): Float32Array {
  if (channels.length === 0) return new Float32Array(0);
  const n = channels[0].length;
  const out = new Float32Array(n);
  for (const ch of channels) for (let i = 0; i < n; i++) out[i] += ch[i] / channels.length;
  return out;
}

/** Playhead x position in pixels. Clamped to the drawing area. */
export function timeToX(time: number, duration: number, width: number): number {
  if (!(duration > 0) || !(width > 0)) return 0;
  return Math.min(width, Math.max(0, (time / duration) * width));
}

/** Inverse of timeToX, for click-to-seek. */
export function xToTime(x: number, duration: number, width: number): number {
  if (!(duration > 0) || !(width > 0)) return 0;
  return Math.min(duration, Math.max(0, (x / width) * duration));
}
