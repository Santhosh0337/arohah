import { useRef, useState } from "react";
import {
  ApiError,
  audioUrl,
  createProject,
  getProject,
  getProjectStatus,
} from "./api/index.ts";
import type { Project, ProjectStatus } from "./api/types.ts";
import { makeFixtureWav } from "./audio/fixtureAudio.ts";
import NewProjectPanel, { type RunView, type StagedClip } from "./components/NewProjectPanel.tsx";
import ProjectView, { type Session } from "./components/ProjectView.tsx";
import { useLanguages } from "./hooks/useLanguages.ts";
import { parseAllowUnverified } from "./lib/languages.ts";
import { toCreateInput, type FormState } from "./lib/newProjectForm.ts";
import { RunError, runProject } from "./lib/projectRun.ts";
import { MOCK_FIXTURE_NOTICE, MOCK_PROJECT } from "./mocks/index.ts";

const ALLOW_UNVERIFIED = parseAllowUnverified(import.meta.env?.VITE_ALLOW_UNVERIFIED_LANGUAGES);

const IDLE_RUN: RunView = { busy: false, status: null, error: null };

export default function App() {
  const langs = useLanguages();
  const [session, setSession] = useState<Session | null>(null);
  const [run, setRun] = useState<RunView>(IDLE_RUN);
  const abort = useRef<AbortController | null>(null);

  const create = async (form: FormState, clip: StagedClip) => {
    const ctl = new AbortController();
    abort.current = ctl;
    setRun({ busy: true, status: null, error: null });
    try {
      const project = await runProject(
        { createProject, getProjectStatus, getProject },
        toCreateInput(form, clip.file),
        {
          signal: ctl.signal,
          onStatus: (status: ProjectStatus) => setRun({ busy: true, status, error: null }),
        },
      );
      setRun(IDLE_RUN);
      setSession({
        kind: "backend",
        project,
        audio: audioUrl(project.payload.input.audio_file_id),
      });
    } catch (e) {
      if (e instanceof RunError && e.code === "aborted") return setRun(IDLE_RUN);
      let message = "Something went wrong while creating the project.";
      if (e instanceof ApiError) {
        message =
          e.code === "network_error"
            ? `${e.message} Start the backend, or use "Preview waveform (no backend)".`
            : e.message;
      } else if (e instanceof RunError) {
        message = e.message;
      }
      setRun({ busy: false, status: null, error: message });
    }
  };

  const previewLocally = (form: FormState, clip: StagedClip) => {
    const base = MOCK_PROJECT;
    const project: Project = {
      ...base,
      id: "local-preview",
      name: form.name.trim() || clip.file.name,
      payload: {
        ...base.payload,
        input: {
          mode: form.mode,
          language: form.mode === "hum" ? null : form.language,
          mixed_language: form.mode === "hum" ? false : form.mixed_language,
          audio_file_id: "",
          duration_s: clip.duration,
        },
        // Fixture lyrics are in Hindi; do not show them next to another language.
        lyrics: [],
        warnings: [],
      },
    };
    setSession({ kind: "local", project, audio: clip.file });
  };

  const loadFixture = () => {
    const { notes_clean, input } = MOCK_PROJECT.payload;
    setSession({
      kind: "fixture",
      project: MOCK_PROJECT,
      audio: makeFixtureWav(notes_clean, input.duration_s),
    });
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Arohah</h1>
        <p className="text-muted">Hum it. Hear it arranged.</p>
      </header>

      {!session && (
        <div role="note" className="mb-6 rounded-sm border-l-4 border-mock bg-mock-bg px-4 py-3 text-sm text-mock">
          {MOCK_FIXTURE_NOTICE} Live Gnani services are not connected in this build, so transcription is not
          available yet.
        </div>
      )}

      {session ? (
        <ProjectView session={session} languages={langs.languages} onNew={() => setSession(null)} />
      ) : (
        <NewProjectPanel
          languages={langs.languages}
          languagesSource={langs.source}
          languagesError={langs.error}
          allowUnverified={ALLOW_UNVERIFIED}
          run={run}
          onCreate={(f, c) => void create(f, c)}
          onCancelRun={() => abort.current?.abort()}
          onPreviewLocally={previewLocally}
          onLoadFixture={loadFixture}
        />
      )}
    </div>
  );
}
