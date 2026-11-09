import { useCallback, useEffect, useRef, useState } from "react";
import type { InputMode, Language, ProjectStatus } from "../api/types.ts";
import { AudioError, decodeAudio } from "../audio/decode.ts";
import { useRecorder, RECORD_CAP_SECONDS } from "../hooks/useRecorder.ts";
import { FILE_ACCEPT, MAX_SECONDS, validateDuration, validateFileFormat } from "../lib/audioValidation.ts";
import { fontStack, isSelectable, isVerified, langAttr } from "../lib/languages.ts";
import {
  MODES,
  initialForm,
  isValid,
  modeUsesLanguage,
  setLanguage,
  setMixedLanguage,
  setMode,
  validateForm,
  type FormState,
} from "../lib/newProjectForm.ts";
import { formatTime } from "../lib/music.ts";

export interface StagedClip {
  file: File;
  duration: number;
}

export interface RunView {
  busy: boolean;
  /** Stage states exactly as the status route reported them. Empty until the first poll. */
  status: ProjectStatus | null;
  error: string | null;
}

interface Props {
  languages: Language[];
  languagesSource: "loading" | "api" | "bundled";
  languagesError: string | null;
  allowUnverified: boolean;
  run: RunView;
  onCreate(form: FormState, clip: StagedClip): void;
  onCancelRun(): void;
  onPreviewLocally(form: FormState, clip: StagedClip): void;
  onLoadFixture(): void;
}

type Source = "record" | "upload";

const fieldCls =
  "w-full rounded-sm border border-line bg-white px-3 py-2 text-base disabled:cursor-not-allowed disabled:bg-ground disabled:text-muted";
const btnPrimary =
  "rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40";
const btnSecondary =
  "rounded-sm border border-accent bg-surface px-4 py-2 text-sm font-medium text-accent disabled:cursor-not-allowed disabled:opacity-40";

export default function NewProjectPanel(props: Props) {
  const { languages, languagesSource, languagesError, allowUnverified, run } = props;
  const [source, setSource] = useState<Source>("record");
  const [form, setForm] = useState<FormState>(initialForm);
  const [clip, setClip] = useState<StagedClip | null>(null);
  const [clipError, setClipError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const stageToken = useRef(0);

  const stageFile = useCallback(async (file: File) => {
    const mine = ++stageToken.current;
    setClip(null);
    setClipError(null);
    const formatError = validateFileFormat(file);
    if (formatError) return setClipError(formatError);
    setChecking(true);
    try {
      const decoded = await decodeAudio(file);
      if (stageToken.current !== mine) return;
      const durationError = validateDuration(decoded.duration);
      if (durationError) setClipError(durationError);
      else setClip({ file, duration: decoded.duration });
    } catch (e) {
      if (stageToken.current === mine) {
        setClipError(e instanceof AudioError ? e.message : "This audio could not be read.");
      }
    } finally {
      if (stageToken.current === mine) setChecking(false);
    }
  }, []);

  const recorder = useRecorder(stageFile);
  const rec = recorder.state;
  const recording = rec.phase !== "idle";
  const recSupport = recorder.support();

  const errors = validateForm(form, languages, allowUnverified);
  const formOk = isValid(errors);
  const ready = formOk && clip !== null && !run.busy;

  // Leaving the Record tab while recording would leave the mic open.
  useEffect(() => {
    if (source !== "record") recorder.cancel();
  }, [source]); // eslint-disable-line react-hooks/exhaustive-deps

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void stageFile(file);
  };

  const submit = (action: "create" | "preview") => {
    setSubmitted(true);
    if (!ready || !clip) return;
    if (action === "create") props.onCreate(form, clip);
    else props.onPreviewLocally(form, clip);
  };

  const remaining = Math.max(0, Math.ceil(RECORD_CAP_SECONDS - rec.elapsed));
  const humHint = !modeUsesLanguage(form.mode);

  return (
    <section aria-labelledby="new-project" className="rounded-md border border-line bg-surface p-6">
      <h2 id="new-project" className="text-xl font-medium">
        New project
      </h2>
      <p className="mb-6 text-sm text-muted">
        Record or upload a clip of {MAX_SECONDS} seconds or less (WAV, MP3, M4A or WebM).
      </p>

      {/* 1. Mode */}
      <fieldset className="mb-6">
        <legend className="mb-2 text-sm font-medium">1. What are you giving us?</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {MODES.map((m) => (
            <label
              key={m.value}
              className={`cursor-pointer rounded-sm border px-3 py-2 ${form.mode === m.value ? "border-accent bg-white ring-1 ring-accent" : "border-line bg-white"}`}
            >
              <input
                type="radio"
                name="mode"
                value={m.value}
                checked={form.mode === m.value}
                onChange={() => setForm((f) => setMode(f, m.value as InputMode))}
                className="mr-2"
              />
              <span className="font-medium">{m.label}</span>
              <span className="block text-sm text-muted">{m.hint}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {/* 2. Language */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="language" className="mb-1 block text-sm font-medium">
            2. Language of the lyrics
          </label>
          <select
            id="language"
            value={form.language}
            disabled={humHint}
            aria-invalid={submitted && !!errors.language}
            aria-describedby="language-help"
            onChange={(e) => setForm((f) => setLanguage(f, e.target.value))}
            className={fieldCls}
          >
            <option value="">{humHint ? "Not needed for humming" : "Choose a language"}</option>
            {languages.map((l) => (
              <option
                key={l.code}
                value={l.code}
                lang={langAttr(l.code)}
                disabled={!isSelectable(l, allowUnverified)}
                style={{ fontFamily: fontStack(l) }}
              >
                {l.native_name === l.name ? l.name : `${l.native_name} (${l.name})`}
                {isVerified(l) ? "" : " - not verified"}
              </option>
            ))}
          </select>
          <p id="language-help" className="mt-1 text-xs text-muted">
            {humHint
              ? "Humming has no language, so none is sent."
              : allowUnverified
                ? "Dev setting on: Prisma support for these languages is not confirmed yet."
                : "Only languages confirmed for transcription can be chosen."}
          </p>
          {submitted && errors.language && (
            <p role="alert" className="mt-1 text-sm text-red-800">
              {errors.language}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="name" className="mb-1 block text-sm font-medium">
            Project name <span className="font-normal text-muted">(optional)</span>
          </label>
          <input
            id="name"
            type="text"
            value={form.name}
            lang={langAttr(form.language)}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Named after the time if empty"
            className={fieldCls}
          />
          {errors.name && (
            <p role="alert" className="mt-1 text-sm text-red-800">
              {errors.name}
            </p>
          )}
          <label className={`mt-3 flex items-center gap-2 text-sm ${humHint ? "text-muted" : ""}`}>
            <input
              type="checkbox"
              checked={form.mixed_language}
              disabled={humHint}
              onChange={(e) => setForm((f) => setMixedLanguage(f, e.target.checked))}
            />
            Mixed language (for example Hinglish or Tanglish)
          </label>
        </div>
      </div>

      {languagesSource === "bundled" && (
        <div role="note" className="mb-6 rounded-sm border-l-4 border-mock bg-mock-bg px-4 py-3 text-sm text-mock">
          Using the bundled language list because the API could not be reached
          {languagesError ? ` (${languagesError})` : ""}. Same data and statuses as the server file.
        </div>
      )}

      {/* 3. Audio */}
      <div className="mb-2 text-sm font-medium">3. Your clip</div>
      <div role="radiogroup" aria-label="Clip source" className="mb-3 inline-flex overflow-hidden rounded-sm border border-line">
        {(
          [
            ["record", "Record"],
            ["upload", "Upload"],
          ] as const
        ).map(([value, text]) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={source === value}
            disabled={recording && value !== source}
            onClick={() => setSource(value)}
            className={`px-4 py-1.5 text-sm ${source === value ? "bg-accent text-white" : "bg-white text-ink"} disabled:opacity-40`}
          >
            {text}
          </button>
        ))}
      </div>

      {source === "record" ? (
        <div className="rounded-sm border border-line bg-white p-4">
          {!recSupport.ok ? (
            <p role="alert" className="text-sm text-red-800">
              {recSupport.reason}
            </p>
          ) : rec.phase === "idle" || rec.phase === "requesting" ? (
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" onClick={() => void recorder.start()} disabled={rec.phase === "requesting"} className={btnPrimary}>
                {rec.phase === "requesting" ? "Waiting for microphone..." : "Start recording"}
              </button>
              <span className="text-sm text-muted">A 3-second countdown follows, then up to {MAX_SECONDS} seconds.</span>
            </div>
          ) : rec.phase === "countdown" ? (
            <div className="flex items-center gap-4" role="status" aria-live="assertive">
              <span className="text-5xl font-semibold tabular-nums text-accent">{rec.countdown}</span>
              <span className="text-sm text-muted">Get ready...</span>
              <button type="button" onClick={recorder.cancel} className={btnSecondary}>
                Cancel
              </button>
            </div>
          ) : rec.phase === "recording" ? (
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-4">
                <span className="inline-flex items-center gap-2 text-sm font-medium">
                  <span aria-hidden className="inline-block h-3 w-3 rounded-full bg-red-700" />
                  Recording {formatTime(rec.elapsed)}
                </span>
                <span className="text-sm tabular-nums text-muted">{remaining} s left</span>
                <button type="button" onClick={recorder.stop} className={btnPrimary}>
                  Stop
                </button>
                <button type="button" onClick={recorder.cancel} className={btnSecondary}>
                  Cancel
                </button>
              </div>
              <div
                role="progressbar"
                aria-label="Recording time used"
                aria-valuemin={0}
                aria-valuemax={Math.round(RECORD_CAP_SECONDS)}
                aria-valuenow={Math.round(rec.elapsed)}
                className="h-1.5 overflow-hidden rounded-sm bg-ground"
              >
                <div className="h-full bg-accent" style={{ width: `${Math.min(100, (rec.elapsed / RECORD_CAP_SECONDS) * 100)}%` }} />
              </div>
            </div>
          ) : (
            <p role="status" className="text-sm text-muted">
              Finishing the recording...
            </p>
          )}
          {rec.error && (
            <p role="alert" className="mt-3 text-sm text-red-800">
              {rec.error}
            </p>
          )}
        </div>
      ) : (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`rounded-sm border-2 border-dashed p-6 text-center ${dragging ? "border-accent bg-white" : "border-line bg-white"}`}
        >
          <p className="text-sm">Drag an audio file here, or</p>
          <button type="button" onClick={() => fileInput.current?.click()} className={`${btnSecondary} mt-2`}>
            Choose a file
          </button>
          <input
            ref={fileInput}
            type="file"
            accept={FILE_ACCEPT}
            hidden
            aria-label="Choose an audio file"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void stageFile(f);
              e.target.value = ""; // allow choosing the same file again
            }}
          />
          <p className="mt-2 text-xs text-muted">WAV, MP3, M4A or WebM. 1 to {MAX_SECONDS} seconds.</p>
        </div>
      )}

      {checking && (
        <p role="status" className="mt-3 text-sm text-muted">
          Checking the clip...
        </p>
      )}
      {clipError && (
        <p role="alert" className="mt-3 text-sm text-red-800">
          {clipError}
        </p>
      )}
      {clip && (
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-sm border border-line bg-white px-3 py-2 text-sm">
          <span className="font-medium">{clip.file.name}</span>
          <span className="text-muted">
            {formatTime(clip.duration)} long, {(clip.file.size / 1024).toFixed(0)} KB
          </span>
          <button
            type="button"
            onClick={() => {
              stageToken.current++;
              setClip(null);
            }}
            className="text-accent underline"
          >
            Remove
          </button>
        </div>
      )}
      {submitted && !clip && !clipError && !checking && (
        <p role="alert" className="mt-3 text-sm text-red-800">
          Record or choose a clip first.
        </p>
      )}

      {/* Actions */}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => submit("create")} disabled={run.busy || checking || recording} className={btnPrimary}>
          {run.busy ? "Working..." : "Create project"}
        </button>
        {run.busy && (
          <button type="button" onClick={props.onCancelRun} className={btnSecondary}>
            Cancel
          </button>
        )}
        <button type="button" onClick={() => submit("preview")} disabled={run.busy || checking || recording} className={btnSecondary}>
          Preview waveform (no backend)
        </button>
        <button type="button" onClick={props.onLoadFixture} disabled={run.busy} className="text-sm text-accent underline">
          Load the fixture project
        </button>
      </div>
      <p className="mt-2 text-xs text-muted">
        "Create project" sends the clip to the API. "Preview" and the fixture project work without a backend and show
        fixture notes, not notes found in your clip.
      </p>

      {/* Real run progress. Nothing here is shown unless the status route answered. */}
      {run.busy && !run.status && (
        <p role="status" className="mt-4 text-sm text-muted">
          Uploading the clip...
        </p>
      )}
      {run.status && (
        <ol className="mt-4 grid gap-1 text-sm sm:grid-cols-2" aria-label="Analysis stages reported by the API">
          {run.status.stages.map((s) => (
            <li key={s.name} className="flex justify-between border-b border-line py-1">
              <span>{s.name}</span>
              <span className={s.state === "failed" ? "text-red-800" : "text-muted"}>{s.state}</span>
            </li>
          ))}
        </ol>
      )}
      {run.error && (
        <p role="alert" className="mt-4 rounded-sm border-l-4 border-red-800 bg-white px-4 py-3 text-sm text-red-800">
          {run.error}
        </p>
      )}
    </section>
  );
}
