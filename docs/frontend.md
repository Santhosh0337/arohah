# Frontend (Person B)

Vite + React + TypeScript + Tailwind 4. Phase B2 adds the New project flow (record, upload, mode, language), a waveform with playback, and a piano roll with a raw/cleaned toggle. The Studio (arrangement, lyrics, voice) comes in later phases.

## Install and run
Built and checked with Node 22 and npm 10.
```bash
cd frontend
cp .env.example .env     # VITE_API_BASE_URL and the dev-only VITE_ALLOW_UNVERIFIED_LANGUAGES
npm install
npm run fonts            # once: downloads the Noto Sans files (needs internet), then commit them
npm run dev              # http://localhost:5173
```
Other scripts: `npm test` (logic tests, Node's built-in runner), `npm run typecheck` (app and tests), `npm run build` (typecheck the app, then build to `dist/`), `npm run preview`.

Microphone recording needs HTTPS or `localhost`.

`VITE_API_BASE_URL` is public and baked in at build time. Never put a secret in a `VITE_` variable. All Gnani calls go through the backend.

## Folder structure
```
frontend/
  index.html  package.json  package-lock.json  vite.config.ts  tsconfig*.json
  .env.example  .gitignore
  scripts/fetch-fonts.mjs  downloads the Noto Sans woff2 files
  public/fonts/            fonts.css, README.md, and the woff2 files once fetched
  src/
    main.tsx  App.tsx  index.css
    api/         types.ts (contract types), client.ts (fetch calls)
    audio/       waveform.ts (peaks), wav.ts, fixtureAudio.ts, decode.ts, player.ts, recorder.ts
    lib/         audioValidation.ts, languages.ts, newProjectForm.ts, pianoRollModel.ts, projectRun.ts, music.ts
    hooks/       useLanguages.ts, useRecorder.ts
    components/  NewProjectPanel, WaveformPlayer, PianoRoll, ProjectView, LangText
    mocks/       dev-only fixtures
    **/*.test.ts logic tests (npm test)
```
Logic lives in `lib/` and `audio/` as plain TypeScript so it can be tested without a browser. Components stay thin.

## The New project flow
1. Choose a mode: Hum, Sing with words, Speak lyrics. Hum disables and clears the language and the mixed-language checkbox, and never sends a language.
2. Sing and Speak need a language from the dropdown (built from `GET /api/languages`). A language is selectable only when `prisma === "confirmed"`. With `VITE_ALLOW_UNVERIFIED_LANGUAGES=true` (dev only) `unconfirmed` ones are selectable too, labelled "not verified". This does not make Prisma work.
3. Record (3-second countdown, then up to about 60 s, remaining time shown) or Upload (click or drag and drop). Accepted: WAV, MP3, M4A, WebM; 1 to 60 s; up to 25 MB. The clip is decoded in the browser to read its length, and bad files get a readable error.
4. Three outcomes:
   - **Create project** posts to `POST /api/projects`, polls the status route once a second and loads the result. The stage list shows only what the API reported. (Async 202 + polling is still `[confirm]`; the code is in `lib/projectRun.ts`.)
   - **Preview waveform (no backend)** shows the real clip with fixture notes. Banner: "Local preview".
   - **Load the fixture project** shows synthetic audio with fixture notes. Banner: "Fixture".
   Results from the API carry the banner "From the API".

## Waveform and piano roll
- `WaveformPlayer`: canvas waveform, play/pause, click or arrow keys to seek, current time and length, resizes with its container. No audio, or audio that cannot be read, shows a message instead of an error screen. The slider is keyboard accessible.
- `PianoRoll`: canvas, MIDI pitch rows labelled with note names (middle C = C4), seconds on the x axis, the playhead from the waveform. Opacity = velocity, dashed outline = confidence under 50%, grey = confidence unknown. Raw shows `notes_raw`, Cleaned shows `notes_clean`; both share one axis range so toggling does not rescale. Hover a note for details. A collapsible table lists every note.

## Fonts
`public/fonts/fonts.css` is linked from `index.html`. Run `npm run fonts` once to download Noto Sans, Noto Sans Tamil and Noto Sans Devanagari (400 and 600) and commit the files. Until then the app uses fonts installed on the machine, then the system stack. Language text is wrapped with `lang` and the `font_family` from `languages.json` (`components/LangText.tsx`, `lib/languages.ts`).

## API client
`import { getProject, arrangeProject, ApiError } from "./api"`. No UI code lives in `src/api/`.
- Reads return the parsed body: `getHealth`, `getLanguages`, `getStyles`, `listProjects`, `getProject`, `getProjectStatus`, `listVersions`.
- `createProject({ audio, mode, language?, mixed_language?, name? })` posts multipart and returns `{ id, status }` (202). Poll `getProjectStatus`, then `getProject`.
- Editing routes (`reanalyzeProject`, `arrangeProject`, `saveLyrics`, `saveVersion`, `duplicateProject`) return `{ data: Project, status }`. Editing a sample forks it (status 201, new `id`), so always use `data.id`.
- `explainProject` and `sendVoiceCommand` call B's routes. The voice route only parses; the UI performs the action (contract section 4).
- URL helpers: `audioUrl`, `absoluteUrl`, `exportMidiUrl`, `exportJsonUrl`.
- Failures throw `ApiError { status, code, message, details }` using the contract's error codes. `code: "network_error"` (status 0) means the API was unreachable.

## Mock fixtures
`src/mocks/` holds shape-only data from contract section 9. It is not real pipeline or Gnani output and is labelled MOCK in names, comments and the UI. `App.tsx` uses it for the fixture project and the local preview, and `hooks/useLanguages.ts` uses the language copy as a fallback when the API is unreachable (with a visible notice). Real sample projects come from real pipeline runs (bible 17.3), never from these files.

## Not built yet (later phases)
Tone.js arrangement playback, A/B playback, analysis cards, arrangement and lyrics panels, live Prisma, Timbre, voice commands. No live Gnani service is connected.
