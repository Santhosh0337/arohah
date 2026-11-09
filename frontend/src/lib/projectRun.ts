// Creates a project and follows its progress.
//
// ASSUMPTION [confirm] (API_CONTRACT 2.4 and open item 1): POST /api/projects
// answers 202 { id, status: "running" } and the client polls
// GET /api/projects/{id}/status about once a second, then loads
// GET /api/projects/{id}. If Person A makes creation synchronous, only this
// file changes. Stage states shown in the UI come from the status route only;
// nothing here invents progress.

import type {
  CreateProjectInput,
  CreateProjectResponse,
  Project,
  ProjectStatus,
} from "../api/types.ts";

export interface RunApi {
  createProject(input: CreateProjectInput): Promise<CreateProjectResponse>;
  getProjectStatus(id: string): Promise<ProjectStatus>;
  getProject(id: string): Promise<Project>;
}

export interface RunOptions {
  intervalMs?: number;
  timeoutMs?: number;
  signal?: AbortSignal;
  onStatus?: (status: ProjectStatus, id: string) => void;
}

export class RunError extends Error {
  readonly code: "pipeline_error" | "timeout" | "aborted";
  readonly projectId?: string;
  constructor(code: RunError["code"], message: string, projectId?: string) {
    super(message);
    this.name = "RunError";
    this.code = code;
    this.projectId = projectId;
  }
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new RunError("aborted", "Cancelled."));
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        reject(new RunError("aborted", "Cancelled."));
      },
      { once: true },
    );
  });

export async function runProject(
  api: RunApi,
  input: CreateProjectInput,
  opts: RunOptions = {},
): Promise<Project> {
  const { intervalMs = 1000, timeoutMs = 120_000, signal, onStatus } = opts;
  const { id } = await api.createProject(input);
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    if (signal?.aborted) throw new RunError("aborted", "Cancelled.", id);
    const status = await api.getProjectStatus(id);
    onStatus?.(status, id);
    if (status.status === "done") return api.getProject(id);
    if (status.status === "error") {
      throw new RunError("pipeline_error", status.error ?? "The analysis failed.", id);
    }
    if (Date.now() >= deadline) {
      throw new RunError("timeout", "The analysis took too long. Try a shorter clip.", id);
    }
    await sleep(intervalMs, signal);
  }
}
