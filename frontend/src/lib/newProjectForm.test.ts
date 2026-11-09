import test from "node:test";
import assert from "node:assert/strict";
import {
  initialForm,
  isValid,
  setLanguage,
  setMixedLanguage,
  setMode,
  toCreateInput,
  validateForm,
  NAME_MAX_LENGTH,
} from "./newProjectForm.ts";
import { isSelectable } from "./languages.ts";
import type { Language } from "../api/types.ts";

const lang = (code: string, prisma: Language["prisma"]): Language => ({
  code,
  name: code,
  native_name: code,
  script: "Latn",
  font_family: "Noto Sans",
  prisma,
  timbre: "unconfirmed",
  command_keywords: false,
  demo: true,
  tested: false,
});
const LANGS = [lang("en-IN", "confirmed"), lang("ta-IN", "unconfirmed"), lang("xx-IN", "unsupported")];
const blob = new Blob(["x"]);

test("hum mode needs no language", () => {
  const form = initialForm();
  assert.equal(form.mode, "hum");
  assert.ok(isValid(validateForm(form, LANGS, false)));
});

test("sing and speak require a language", () => {
  for (const mode of ["sing", "speak"] as const) {
    const form = setMode(initialForm(), mode);
    assert.match(validateForm(form, LANGS, false).language!, /Choose the language/);
    assert.ok(isValid(validateForm(setLanguage(form, "en-IN"), LANGS, false)));
  }
});

test("an unknown language code is rejected", () => {
  const form = setLanguage(setMode(initialForm(), "sing"), "zz-ZZ");
  assert.match(validateForm(form, LANGS, true).language!, /not in the list/);
});

test("unconfirmed languages need the dev switch; unsupported never pass", () => {
  const form = setLanguage(setMode(initialForm(), "sing"), "ta-IN");
  assert.match(validateForm(form, LANGS, false).language!, /not verified/);
  assert.ok(isValid(validateForm(form, LANGS, true)));
  const bad = setLanguage(setMode(initialForm(), "sing"), "xx-IN");
  assert.match(validateForm(bad, LANGS, true).language!, /not verified/);
  assert.equal(isSelectable(LANGS[2], true), false);
});

test("switching to hum clears language and mixed-language", () => {
  let form = setMode(initialForm(), "sing");
  form = setMixedLanguage(setLanguage(form, "en-IN"), true);
  assert.equal(form.mixed_language, true);
  form = setMode(form, "hum");
  assert.equal(form.language, "");
  assert.equal(form.mixed_language, false);
});

test("hum ignores language and mixed-language changes", () => {
  const form = initialForm();
  assert.deepEqual(setLanguage(form, "en-IN"), form);
  assert.deepEqual(setMixedLanguage(form, true), form);
});

test("mixed-language is kept when switching between sing and speak", () => {
  let form = setMixedLanguage(setLanguage(setMode(initialForm(), "sing"), "en-IN"), true);
  form = setMode(form, "speak");
  assert.equal(form.mixed_language, true);
  assert.equal(form.language, "en-IN");
});

test("name length is limited by characters, not UTF-16 units", () => {
  const ok = { ...initialForm(), name: "த".repeat(NAME_MAX_LENGTH) };
  assert.ok(isValid(validateForm(ok, LANGS, false)));
  const long = { ...initialForm(), name: "த".repeat(NAME_MAX_LENGTH + 1) };
  assert.match(validateForm(long, LANGS, false).name!, /characters or fewer/);
});

test("hum request omits language and mixed_language", () => {
  const input = toCreateInput(initialForm(), blob);
  assert.equal(input.mode, "hum");
  assert.equal("language" in input, false);
  assert.equal("mixed_language" in input, false);
  assert.equal("name" in input, false);
});

test("sing request carries language, mixed flag and a trimmed NFC name", () => {
  let form = setMixedLanguage(setLanguage(setMode(initialForm(), "sing"), "ta-IN"), true);
  form = { ...form, name: "  étude  " }; // e + combining acute
  const input = toCreateInput(form, blob);
  assert.equal(input.language, "ta-IN");
  assert.equal(input.mixed_language, true);
  assert.equal(input.name, "étude");
});
