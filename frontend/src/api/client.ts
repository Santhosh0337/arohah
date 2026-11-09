// Thin client for the Arohah API (docs/API_CONTRACT.md). No UI code in here.

import type {
  ApiErrorBody,
  ArrangeInput,
  CreateProjectInput,
  CreateProjectResponse,
  ExplainInput,
  ExplainResponse,
  HealthResponse,
  Language,
  Project,
  ProjectStatus,
  ProjectSummary,
  ReanalyzeInput,
  StyleInfo,
  VersionInfo,
  VoiceCommandInput,
  VoiceCommandResponse,
  LyricWord,
} from "./types";

export const API_BASE_URL: string = (
  import.meta.env?.VITE_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/** A result plus the HTTP status, for the editing routes that answer 200 or 201. */
export interface WithStatus<T> {
  data: T;
  status: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<WithStatus<T>> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(0, "network_error", `Could not reach the API at ${API_BASE_URL}.`);
  }
  if (!res.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    const e = body.error;
    throw new ApiError(
      res.status,
      e?.code ?? "internal",
      e?.message ?? `Request failed with status ${res.status}.`,
      e?.details ?? {},
    );
  }
  return { data: (await res.json()) as T, status: res.status };
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

const get = async <T>(path: string) => (await request<T>(path)).data;

// ---- URL helpers (for <audio>, wavesurfer and download links) ----
export const audioUrl = (fileId: string) => `${API_BASE_URL}/api/audio/${fileId}`;
/** The explain route returns a path ("/api/audio/<id>"); make it absolute. */
export const absoluteUrl = (path: string) => `${API_BASE_URL}${path}`;
export const exportMidiUrl = (id: string) => `${API_BASE_URL}/api/projects/${id}/export/midi`;
export const exportJsonUrl = (id: string) => `${API_BASE_URL}/api/projects/${id}/export/json`;

// ---- Routes ----
export const getHealth = () => get<HealthResponse>("/api/health");

export const getLanguages = async () =>
  (await get<{ languages: Language[] }>("/api/languages")).languages;

export const getStyles = async () =>
  (await get<{ styles: StyleInfo[] }>("/api/styles")).styles;

export function createProject(input: CreateProjectInput) {
  const form = new FormData();
  form.append("audio", input.audio);
  form.append("mode", input.mode);
  if (input.language) form.append("language", input.language);
  if (input.mixed_language !== undefined)
    form.append("mixed_language", String(input.mixed_language));
  if (input.name) form.append("name", input.name);
  return request<CreateProjectResponse>("/api/projects", { method: "POST", body: form }).then(
    (r) => r.data,
  );
}

export const getProjectStatus = (id: string) => get<ProjectStatus>(`/api/projects/${id}/status`);

export const listProjects = async () =>
  (await get<{ projects: ProjectSummary[] }>("/api/projects")).projects;

export const getProject = (id: string) => get<Project>(`/api/projects/${id}`);

/**
 * Editing routes (reanalyze, arrange, lyrics, versions, duplicate).
 * Editing a sample forks it: the response is 201 with a NEW id. Always use
 * `data.id` from the result, never the id you sent.
 */
export const reanalyzeProject = (id: string, body: ReanalyzeInput = {}) =>
  request<Project>(`/api/projects/${id}/reanalyze`, json("POST", body));

export const arrangeProject = (id: string, body: ArrangeInput = {}) =>
  request<Project>(`/api/projects/${id}/arrange`, json("POST", body));

export const saveLyrics = (id: string, lyrics: LyricWord[]) =>
  request<Project>(`/api/projects/${id}/lyrics`, json("PUT", { lyrics }));

export const saveVersion = (id: string, label: string) =>
  request<Project>(`/api/projects/${id}/versions`, json("POST", { label }));

export const listVersions = async (id: string) =>
  (await get<{ versions: VersionInfo[] }>(`/api/projects/${id}/versions`)).versions;

export const duplicateProject = (id: string) =>
  request<Project>(`/api/projects/${id}/duplicate`, { method: "POST" });

export const explainProject = (id: string, body: ExplainInput) =>
  request<ExplainResponse>(`/api/projects/${id}/explain`, json("POST", body)).then((r) => r.data);

export function sendVoiceCommand(input: VoiceCommandInput) {
  const form = new FormData();
  form.append("audio", input.audio);
  form.append("language", input.language);
  if (input.project_id) form.append("project_id", input.project_id);
  return request<VoiceCommandResponse>("/api/voice/command", {
    method: "POST",
    body: form,
  }).then((r) => r.data);
}
