import type {
  CreateProjectInput,
  CreateProjectResponse,
  Language,
  Project,
  ProjectStatus,
} from "./types.ts";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export type ApiErrorCode = "network_error" | "validation_error" | "not_found" | "provider_unavailable" | "provider_timeout" | "internal" | string;

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly status: number | null;

  constructor(code: ApiErrorCode, message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("network_error", "Could not reach the Arohah backend.");
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const root = body && typeof body === "object" ? body as Record<string, unknown> : {};
    const error = root.error && typeof root.error === "object"
      ? root.error as Record<string, unknown>
      : root.detail && typeof root.detail === "object"
        ? (root.detail as Record<string, unknown>).error as Record<string, unknown> | undefined
        : undefined;
    const code = typeof error?.code === "string" ? error.code : "internal";
    const message = typeof error?.message === "string" ? error.message : `Request failed (${response.status}).`;
    throw new ApiError(code, message, response.status);
  }
  return body as T;
}

export async function getLanguages(): Promise<Language[]> {
  const result = await request<{ languages: Language[] }>("/api/languages");
  return result.languages;
}

export function createProject(input: CreateProjectInput): Promise<CreateProjectResponse> {
  const form = new FormData();
  form.append("audio", input.audio);
  form.append("mode", input.mode);
  if (input.language !== undefined) form.append("language", input.language);
  if (input.mixed_language !== undefined) form.append("mixed_language", String(input.mixed_language));
  if (input.name !== undefined) form.append("name", input.name);
  return request<CreateProjectResponse>("/api/projects", { method: "POST", body: form });
}

export function getProjectStatus(id: string): Promise<ProjectStatus> {
  return request<ProjectStatus>(`/api/projects/${encodeURIComponent(id)}/status`);
}

export function getProject(id: string): Promise<Project> {
  return request<Project>(`/api/projects/${encodeURIComponent(id)}`);
}

export function audioUrl(fileId: string): string {
  return `${API_BASE}/api/audio/${encodeURIComponent(fileId)}`;
}
