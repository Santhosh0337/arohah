import { useState } from "react";
import type { Language, Project } from "../api/types.ts";
import { findLanguage } from "../lib/languages.ts";
import LangText from "./LangText.tsx";
import PianoRoll from "./PianoRoll.tsx";
import WaveformPlayer from "./WaveformPlayer.tsx";

export type SessionKind = "fixture" | "local" | "backend";

export interface Session {
  kind: SessionKind;
  project: Project;
  audio: Blob | string | null;
}

const BADGE: Record<SessionKind, { text: string; detail: string; fixture: boolean }> = {
  fixture: {
    text: "Fixture",
    detail: "Synthetic audio and made-up notes. Nothing here came from a recording or from Gnani.",
    fixture: true,
  },
  local: {
    text: "Local preview",
    detail:
      "The waveform is your real clip. The notes are fixture data: they were NOT extracted from your clip, and no backend was used.",
    fixture: true,
  },
  backend: {
    text: "From the API",
    detail: "Audio and notes returned by the backend for this project.",
    fixture: false,
  },
};

const PROVENANCE: Record<SessionKind, string> = {
  fixture: "Notes: fixture data, not extracted from audio.",
  local: "Notes: fixture data, not extracted from your clip.",
  backend: "Notes: from the backend pipeline (pYIN with rule-based cleanup). Confidence is approximate.",
};

export default function ProjectView({
  session,
  languages,
  onNew,
}: {
  session: Session;
  languages: Language[];
  onNew(): void;
}) {
  const [position, setPosition] = useState(0);
  const { project, kind, audio } = session;
  const { payload } = project;
  const badge = BADGE[kind];
  const lang = findLanguage(languages, payload.input.language);

  return (
    <section aria-labelledby="project-title" className="rounded-md border border-line bg-surface p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="project-title" className="text-xl font-medium">
            <LangText language={lang} code={payload.input.language}>
              {project.name}
            </LangText>
          </h2>
          <p className="text-sm text-muted">
            {payload.input.mode} mode
            {lang ? `, ${lang.name}` : ""}
            {payload.input.mixed_language ? ", mixed language" : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={onNew}
          className="rounded-sm border border-accent bg-surface px-4 py-2 text-sm font-medium text-accent"
        >
          New project
        </button>
      </div>

      <div
        role="note"
        className={`mb-6 rounded-sm border-l-4 px-4 py-3 text-sm ${badge.fixture ? "border-mock bg-mock-bg text-mock" : "border-accent bg-white"}`}
      >
        <strong>{badge.text}.</strong> {badge.detail}
      </div>

      <div className="mb-8">
        <WaveformPlayer source={audio} label="Waveform" onPosition={setPosition} />
      </div>

      <PianoRoll
        notesRaw={payload.notes_raw}
        notesClean={payload.notes_clean}
        durationS={payload.input.duration_s}
        position={position}
        provenance={PROVENANCE[kind]}
      />

      {kind === "backend" && payload.warnings.length > 0 && (
        <ul className="mt-6 text-sm" aria-label="Warnings from the pipeline">
          {payload.warnings.map((w, i) => (
            <li key={i} className="border-l-4 border-mock bg-mock-bg px-3 py-1 text-mock">
              {w.stage}: {w.message}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
