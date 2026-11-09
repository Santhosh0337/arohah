import test from "node:test";
import assert from "node:assert/strict";
import { RunError, runProject, type RunApi } from "./projectRun.ts";
import { MOCK_PROJECT } from "../mocks/exampleProject.ts";
import type { ProjectStatus } from "../api/types.ts";

const status = (s: ProjectStatus["status"], stage: ProjectStatus["stage"] = "pitch"): ProjectStatus => ({
  status: s,
  stage,
  stages: [],
  error: s === "error" ? "boom" : null,
});

function fakeApi(sequence: ProjectStatus[]): RunApi & { polls: number } {
  const api = {
    polls: 0,
    createProject: async () => ({ id: "abc", status: "running" as const }),
    getProjectStatus: async () => sequence[Math.min(api.polls++, sequence.length - 1)],
    getProject: async () => MOCK_PROJECT,
  };
  return api;
}

const input = { audio: new Blob(["x"]), mode: "hum" as const };

test("polls until done, reports each status, then loads the project", async () => {
  const api = fakeApi([status("running"), status("running", "cleanup"), status("done", null)]);
  const seen: string[] = [];
  const project = await runProject(api, input, {
    intervalMs: 0,
    onStatus: (s) => seen.push(s.status),
  });
  assert.equal(project, MOCK_PROJECT);
  assert.deepEqual(seen, ["running", "running", "done"]);
});

test("a pipeline error becomes a RunError with the server message", async () => {
  await assert.rejects(
    runProject(fakeApi([status("error")]), input, { intervalMs: 0 }),
    (e: unknown) => e instanceof RunError && e.code === "pipeline_error" && e.message === "boom",
  );
});

test("gives up after the timeout", async () => {
  await assert.rejects(
    runProject(fakeApi([status("running")]), input, { intervalMs: 0, timeoutMs: 5 }),
    (e: unknown) => e instanceof RunError && e.code === "timeout",
  );
});

test("an aborted run stops polling", async () => {
  const ctl = new AbortController();
  const api = fakeApi([status("running")]);
  setTimeout(() => ctl.abort(), 5);
  await assert.rejects(
    runProject(api, input, { intervalMs: 20, signal: ctl.signal }),
    (e: unknown) => e instanceof RunError && e.code === "aborted",
  );
});
