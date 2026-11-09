// Plays one decoded AudioBuffer with seek support. Used by the waveform.
// A buffer source (not an <audio> element) is used because MediaRecorder WebM
// files often cannot seek and report an unknown length.

export class BufferPlayer {
  readonly duration: number;
  playing = false;
  onEnded: (() => void) | null = null;

  #ctx: AudioContext;
  #buffer: AudioBuffer;
  #source: AudioBufferSourceNode | null = null;
  #startedAtCtx = 0;
  #offset = 0;

  constructor(ctx: AudioContext, buffer: AudioBuffer) {
    this.#ctx = ctx;
    this.#buffer = buffer;
    this.duration = buffer.duration;
  }

  /** Current position in seconds. */
  get position(): number {
    if (!this.playing) return this.#offset;
    return Math.min(this.duration, this.#offset + (this.#ctx.currentTime - this.#startedAtCtx));
  }

  async play(): Promise<void> {
    if (this.playing) return;
    if (this.#ctx.state === "suspended") await this.#ctx.resume();
    if (this.#offset >= this.duration - 0.01) this.#offset = 0;
    const src = this.#ctx.createBufferSource();
    src.buffer = this.#buffer;
    src.connect(this.#ctx.destination);
    src.onended = () => {
      if (this.#source !== src) return; // replaced by pause or seek
      this.#source = null;
      this.playing = false;
      this.#offset = this.duration;
      this.onEnded?.();
    };
    this.#startedAtCtx = this.#ctx.currentTime;
    src.start(0, this.#offset);
    this.#source = src;
    this.playing = true;
  }

  pause(): void {
    if (!this.playing) return;
    this.#offset = this.position;
    this.#stopSource();
    this.playing = false;
  }

  seek(seconds: number): void {
    const t = Math.min(this.duration, Math.max(0, seconds));
    const resume = this.playing;
    this.#stopSource();
    this.playing = false;
    this.#offset = t;
    if (resume) void this.play();
  }

  dispose(): void {
    this.#stopSource();
    this.playing = false;
    this.onEnded = null;
  }

  #stopSource(): void {
    const src = this.#source;
    this.#source = null;
    if (src) {
      src.onended = null;
      try {
        src.stop();
      } catch {
        /* already stopped */
      }
      src.disconnect();
    }
  }
}
