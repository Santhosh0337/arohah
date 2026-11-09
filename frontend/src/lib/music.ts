// Small music helpers shared by the piano roll and the fixtures.

export const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"] as const;

const BLACK = new Set([1, 3, 6, 8, 10]);

/** MIDI pitch to a name with octave. Middle C (60) is "C4". */
export function noteName(midi: number): string {
  const pc = ((Math.round(midi) % 12) + 12) % 12;
  return `${NOTE_NAMES[pc]}${Math.floor(Math.round(midi) / 12) - 1}`;
}

export function isBlackKey(midi: number): boolean {
  return BLACK.has(((Math.round(midi) % 12) + 12) % 12);
}

/** "1:05.3" style clock for the waveform. */
export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00.0";
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}
