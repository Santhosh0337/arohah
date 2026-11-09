// Client-side checks for audio clips. The server repeats them (contract
// section 3: audio_too_short, audio_too_long, unsupported_format); these give
// the user an answer before anything is uploaded.

export const MIN_SECONDS = 1;
export const MAX_SECONDS = 60;
/** Not fixed by the contract. A 60 s stereo WAV at 44.1 kHz is about 10 MB. */
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

export const ACCEPTED_EXTENSIONS = ["wav", "mp3", "m4a", "webm"] as const;
export type AcceptedExtension = (typeof ACCEPTED_EXTENSIONS)[number];

const MIME_BY_EXTENSION: Record<AcceptedExtension, string[]> = {
  wav: ["audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"],
  mp3: ["audio/mpeg", "audio/mp3"],
  m4a: ["audio/mp4", "audio/x-m4a", "audio/m4a", "audio/aac"],
  webm: ["audio/webm", "video/webm"],
};

const ALL_MIMES = new Set(Object.values(MIME_BY_EXTENSION).flat());

/** Value for <input type="file" accept>. */
export const FILE_ACCEPT = [
  ...ACCEPTED_EXTENSIONS.map((e) => `.${e}`),
  ...ALL_MIMES,
].join(",");

export function fileExtension(name: string): string {
  const i = name.lastIndexOf(".");
  return i < 0 ? "" : name.slice(i + 1).toLowerCase();
}

/** "audio/webm;codecs=opus" -> "audio/webm" */
export function baseMime(type: string): string {
  return type.split(";")[0].trim().toLowerCase();
}

export function isAcceptedExtension(ext: string): ext is AcceptedExtension {
  return (ACCEPTED_EXTENSIONS as readonly string[]).includes(ext);
}

export function extensionForMime(type: string): AcceptedExtension | null {
  const mime = baseMime(type);
  for (const ext of ACCEPTED_EXTENSIONS) {
    if (MIME_BY_EXTENSION[ext].includes(mime)) return ext;
  }
  return null;
}

export interface FileLike {
  name: string;
  type: string;
  size: number;
}

/** Returns an error message, or null when the file is acceptable. */
export function validateFileFormat(file: FileLike): string | null {
  const ext = fileExtension(file.name);
  if (!isAcceptedExtension(ext)) {
    return `Unsupported file type${ext ? ` ".${ext}"` : ""}. Use WAV, MP3, M4A or WebM.`;
  }
  const mime = baseMime(file.type);
  // Some systems report an empty or odd type for valid files, so only reject a
  // type that is clearly not one of ours.
  if (mime && !ALL_MIMES.has(mime)) {
    return `This file reports type "${mime}", which is not WAV, MP3, M4A or WebM audio.`;
  }
  if (file.size <= 0) return "This file is empty.";
  if (file.size > MAX_UPLOAD_BYTES) {
    return `This file is ${(file.size / 1048576).toFixed(1)} MB. The limit is ${MAX_UPLOAD_BYTES / 1048576} MB.`;
  }
  return null;
}

/** Returns an error message, or null when the duration is within 1 to 60 s. */
export function validateDuration(seconds: number): string | null {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "Could not read the length of this audio.";
  }
  if (seconds < MIN_SECONDS) {
    return `This clip is ${seconds.toFixed(1)} s. It must be at least ${MIN_SECONDS} s.`;
  }
  if (seconds > MAX_SECONDS) {
    return `This clip is ${seconds.toFixed(1)} s. It must be ${MAX_SECONDS} s or less.`;
  }
  return null;
}
