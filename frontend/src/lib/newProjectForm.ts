// Pure logic for the New project form (F32, F33). No React in here so it can
// be tested with `npm test`.

import type { CreateProjectInput, InputMode, Language } from "../api/types.ts";
import { isSelectable, nfc } from "./languages.ts";

export const MODES: { value: InputMode; label: string; hint: string }[] = [
  { value: "hum", label: "Hum", hint: "No words. Lyrics are skipped." },
  { value: "sing", label: "Sing with words", hint: "Lyrics are transcribed." },
  { value: "speak", label: "Speak lyrics", hint: "Lyrics are transcribed." },
];

export const NAME_MAX_LENGTH = 80;

export interface FormState {
  mode: InputMode;
  /** Language code, "" when none is chosen. Always "" in hum mode. */
  language: string;
  mixed_language: boolean;
  name: string;
}

export interface FormErrors {
  language?: string;
  name?: string;
}

export function initialForm(): FormState {
  return { mode: "hum", language: "", mixed_language: false, name: "" };
}

export const modeUsesLanguage = (mode: InputMode) => mode !== "hum";

/** Hum has no language and no mixed-language setting, so both are cleared. */
export function setMode(state: FormState, mode: InputMode): FormState {
  if (!modeUsesLanguage(mode)) return { ...state, mode, language: "", mixed_language: false };
  return { ...state, mode };
}

export function setLanguage(state: FormState, language: string): FormState {
  if (!modeUsesLanguage(state.mode)) return state;
  return { ...state, language };
}

export function setMixedLanguage(state: FormState, mixed: boolean): FormState {
  if (!modeUsesLanguage(state.mode)) return state;
  return { ...state, mixed_language: mixed };
}

export function validateForm(
  state: FormState,
  languages: Language[],
  allowUnverified: boolean,
): FormErrors {
  const errors: FormErrors = {};
  if (modeUsesLanguage(state.mode)) {
    const lang = languages.find((l) => l.code === state.language);
    if (!state.language) {
      errors.language = "Choose the language of the lyrics.";
    } else if (!lang) {
      errors.language = "This language is not in the list.";
    } else if (!isSelectable(lang, allowUnverified)) {
      errors.language = `${lang.name} is not verified for transcription yet.`;
    }
  }
  const name = state.name.trim();
  if ([...name].length > NAME_MAX_LENGTH) {
    errors.name = `Use ${NAME_MAX_LENGTH} characters or fewer.`;
  }
  return errors;
}

export const isValid = (errors: FormErrors) => Object.keys(errors).length === 0;

/** Builds the POST /api/projects input. Hum never sends a language. */
export function toCreateInput(state: FormState, audio: Blob | File): CreateProjectInput {
  const input: CreateProjectInput = { audio, mode: state.mode };
  if (modeUsesLanguage(state.mode)) {
    input.language = state.language;
    input.mixed_language = state.mixed_language;
  }
  const name = nfc(state.name.trim());
  if (name) input.name = name;
  return input;
}
