import { useCallback, useEffect, useRef, useState } from "react";
import { decodeAudio } from "../audio/decode.ts";
import {
  describeMicError,
  describeRecording,
  openMicrophone,
  recordingSupport,
  startRecording,
  type RecorderHandle,
} from "../audio/recorder.ts";
import { encodeWav } from "../audio/wav.ts";
import { MAX_SECONDS } from "../lib/audioValidation.ts";

/** Stop a little early so the decoded clip never lands just over 60 s. */
export const RECORD_CAP_SECONDS = MAX_SECONDS - 0.5;
const COUNTDOWN_FROM = 3;

export type RecorderPhase = "idle" | "requesting" | "countdown" | "recording" | "processing";

export interface RecorderState {
  phase: RecorderPhase;
  countdown: number;
  elapsed: number;
  error: string | null;
}

export function useRecorder(onClip: (file: File) => void) {
  const [state, setState] = useState<RecorderState>({
    phase: "idle",
    countdown: 0,
    elapsed: 0,
    error: null,
  });
  const handle = useRef<RecorderHandle | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const token = useRef(0); // bumped to invalidate an in-flight start
  const onClipRef = useRef(onClip);
  onClipRef.current = onClip;

  const reset = useCallback((error: string | null = null) => {
    window.clearTimeout(timer.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    handle.current = null;
    setState({ phase: "idle", countdown: 0, elapsed: 0, error });
  }, []);

  const start = useCallback(async () => {
    const support = recordingSupport();
    if (!support.ok) return reset(support.reason);
    const mine = ++token.current;
    setState({ phase: "requesting", countdown: 0, elapsed: 0, error: null });

    let mic: MediaStream;
    try {
      mic = await openMicrophone();
    } catch (e) {
      if (token.current === mine) reset(describeMicError(e));
      return;
    }
    if (token.current !== mine) {
      mic.getTracks().forEach((t) => t.stop());
      return;
    }
    stream.current = mic;

    const tick = (n: number) => {
      if (token.current !== mine) return;
      if (n === 0) {
        setState({ phase: "recording", countdown: 0, elapsed: 0, error: null });
        handle.current = startRecording(
          mic,
          {
            onTick: (elapsed) => token.current === mine && setState((s) => ({ ...s, elapsed })),
            onError: (message) => token.current === mine && reset(message),
            onDone: async (result) => {
              if (token.current !== mine) return;
              stream.current = null;
              handle.current = null;
              setState((s) => ({ ...s, phase: "processing" }));
              try {
                const { fileName, accepted } = describeRecording(result.mime);
                let file: File;
                if (accepted) {
                  file = new File([result.blob], fileName, { type: result.mime });
                } else {
                  // e.g. Firefox records OGG, which the API does not accept.
                  const decoded = await decodeAudio(result.blob);
                  const wav = encodeWav(decoded.mono, decoded.buffer.sampleRate);
                  file = new File([wav.buffer as ArrayBuffer], fileName, { type: "audio/wav" });
                }
                if (token.current !== mine) return;
                reset();
                onClipRef.current(file);
              } catch (e) {
                if (token.current === mine) {
                  reset(e instanceof Error ? e.message : "Could not process the recording.");
                }
              }
            },
          },
          RECORD_CAP_SECONDS,
        );
        return;
      }
      setState({ phase: "countdown", countdown: n, elapsed: 0, error: null });
      timer.current = window.setTimeout(() => tick(n - 1), 1000);
    };
    tick(COUNTDOWN_FROM);
  }, [reset]);

  const stop = useCallback(() => handle.current?.stop(), []);

  const cancel = useCallback(() => {
    token.current++;
    handle.current?.cancel();
    reset();
  }, [reset]);

  useEffect(
    () => () => {
      token.current++;
      handle.current?.cancel();
      window.clearTimeout(timer.current);
      stream.current?.getTracks().forEach((t) => t.stop());
    },
    [],
  );

  return { state, start, stop, cancel, support: recordingSupport };
}
