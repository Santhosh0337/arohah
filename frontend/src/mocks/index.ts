import type { Language } from "../api/types.ts";
import { MOCK_PROJECT } from "./exampleProject.ts";

export { MOCK_PROJECT };

// Mirrors backend/data/languages.json from Phase B1. Provider statuses remain
// unconfirmed; the UI must not present them as live-ready languages.
export const MOCK_LANGUAGES: Language[] = [
  {
    code: "en-IN", name: "English", native_name: "English", script: "Latn",
    font_family: "Noto Sans", prisma: "unconfirmed", timbre: "unconfirmed",
    command_keywords: false, demo: true, tested: false,
  },
  {
    code: "ta-IN", name: "Tamil", native_name: "தமிழ்", script: "Taml",
    font_family: "Noto Sans Tamil", prisma: "unconfirmed", timbre: "unconfirmed",
    command_keywords: false, demo: true, tested: false,
  },
  {
    code: "hi-IN", name: "Hindi", native_name: "हिन्दी", script: "Deva",
    font_family: "Noto Sans Devanagari", prisma: "unconfirmed", timbre: "unconfirmed",
    command_keywords: false, demo: true, tested: false,
  },
];

export const MOCK_FIXTURE_NOTICE =
  "Demo mode: fixture data is used unless the backend is connected.";
