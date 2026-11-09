// Microphone recording with MediaRecorder (F1, F32).

import { MAX_SECONDS, baseMime, extensionForMime } from "../lib/audioValidation.ts";

export type SupportResult = { ok: true } | { ok: false; reason: string };

/** Checks the browser can record. Safe to call during render. */
export function recordingSupport(): SupportResult {
  if (typeof window === "undefined") return { ok: false, reason: "Recording needs a browser." };
  if (!window.isSecureContext) {
    return { ok: false, reason: "Recording needs HTTPS or localhost. Use Upload instead." };
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return { ok: false, reason: "This browser cannot access the microphone. Use Upload instead." };
  }
  if (typeof MediaRecorder === "undefined") {
    return { ok: false, reason: "This browser cannot record audio. Use Upload instead." };
  }
  return { ok: true };
}

const PREFERRED_MIMES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

/** First preferred container this browser supports, or undefined to let it choose. */
export function pickRecorderMime(
  isSupported: (m: string) => boolean = (m) =>
    typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(m),
): string | undefined {
  return PREFERRED_MIMES.find((m) => isSupported(m));
}

/** Plain-language message for a getUserMedia failure. */
export function describeMicError(err: unknown): string {
  const name = err instanceof DOMException || err instanceof Error ? err.name : "";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Microphone permission was denied. Allow it in the browser's site settings, or use Upload.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "No microphone was found. Connect one, or use Upload.";
    case "NotReadableError":
    case "AbortError":
      return "The microphone is busy or unavailable. Close other apps using it and try again.";
    default:
      return "Could not start the microphone. Try again, or use Upload.";
  }
}

export interface RecordingResult {
  blob: Blob;
  /** Container reported by MediaRecorder, for example "audio/webm" */
  mime: string;
  seconds: number;
}

export interface RecorderHandle {
  stop(): void;
  cancel(): void;
}

export interface RecorderCallbacks {
  onTick(elapsedSeconds: number): void;
  onDone(result: RecordingResult): void;
  onError(message: string): void;
}

/** Opens the microphone only. Call startRecording with the returned stream. */
export async function openMicrophone(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({ audio: true });
}

export function startRecording(
  stream: MediaStream,
  cb: RecorderCallbacks,
  maxSeconds = MAX_SECONDS,
): RecorderHandle {
  const mime = pickRecorderMime();
  let recorder: MediaRecorder;
  try {
    recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
  } catch {
    stream.getTracks().forEach((t) => t.stop());
    cb.onError("Could not start recording in this browser. Use Upload instead.");
    return { stop() {}, cancel() {} };
  }

  const chunks: Blob[] = [];
  const t0 = performance.now();
  let cancelled = false;
  let finished = false;

  const releaseMic = () => stream.getTracks().forEach((t) => t.stop());
  const timer = window.setInterval(() => {
    const elapsed = (performance.now() - t0) / 1000;
    cb.onTick(Math.min(elapsed, maxSeconds));
    if (elapsed >= maxSeconds && recorder.state === "recording") recorder.stop();
  }, 100);

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };
  recorder.onerror = () => {
    if (finished) return;
    finished = true;
    window.clearInterval(timer);
    releaseMic();
    cb.onError("The recording failed. Try again, or use Upload.");
  };
  recorder.onstop = () => {
    window.clearInterval(timer);
    releaseMic();
    if (finished || cancelled) return;
    finished = true;
    const type = baseMime(recorder.mimeType || mime || "");
    const blob = new Blob(chunks, { type: type || "audio/webm" });
    if (blob.size === 0) {
      cb.onError("Nothing was recorded. Check the microphone and try again.");
      return;
    }
    cb.onDone({ blob, mime: type, seconds: Math.min((performance.now() - t0) / 1000, maxSeconds) });
  };

  recorder.start(250);
  return {
    stop() {
      if (recorder.state === "recording") recorder.stop();
    },
    cancel() {
      cancelled = true;
      if (recorder.state !== "inactive") recorder.stop();
      else releaseMic();
    },
  };
}

/**
 * Names a recording and tells whether the API accepts its container. WebM and
 * MP4 (M4A) are accepted; others (Firefox records OGG) must be converted to WAV
 * by the caller.
 */
export function describeRecording(mime: string): { fileName: string; accepted: boolean } {
  const ext = extensionForMime(mime);
  return ext ? { fileName: `recording.${ext}`, accepted: true } : { fileName: "recording.wav", accepted: false };
}
