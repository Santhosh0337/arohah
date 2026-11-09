// Browser audio decoding. Needs Web Audio, so it is not unit tested in Node.

import { mixToMono } from "./waveform.ts";

let sharedContext: AudioContext | null = null;

export function getAudioContext(): AudioContext {
  if (!sharedContext) {
    const Ctor: typeof AudioContext | undefined =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) throw new AudioError("This browser cannot decode audio (Web Audio is missing).");
    sharedContext = new Ctor();
  }
  return sharedContext;
}

export class AudioError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AudioError";
  }
}

export interface DecodedAudio {
  buffer: AudioBuffer;
  duration: number;
  /** Mono mix for drawing */
  mono: Float32Array;
}

/** Decodes a Blob/File, or fetches and decodes a URL (for example /api/audio/<id>). */
export async function decodeAudio(source: Blob | string): Promise<DecodedAudio> {
  let data: ArrayBuffer;
  if (typeof source === "string") {
    let res: Response;
    try {
      res = await fetch(source);
    } catch {
      throw new AudioError("Could not download the audio. Is the API running?");
    }
    if (!res.ok) throw new AudioError(`The audio could not be loaded (status ${res.status}).`);
    data = await res.arrayBuffer();
  } else {
    data = await source.arrayBuffer();
  }
  if (data.byteLength === 0) throw new AudioError("The audio is empty.");
  let buffer: AudioBuffer;
  try {
    buffer = await getAudioContext().decodeAudioData(data);
  } catch {
    throw new AudioError(
      "This browser could not read the audio. The file may be damaged or in a format it cannot play. Try WAV or MP3.",
    );
  }
  const channels = Array.from({ length: buffer.numberOfChannels }, (_, i) => buffer.getChannelData(i));
  return { buffer, duration: buffer.duration, mono: mixToMono(channels) };
}
