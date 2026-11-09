// MOCK FIXTURE. Development only. Mirrors backend/data/languages.json so the
// UI can build language dropdowns before GET /api/languages exists.
// Provider support is deliberately "unconfirmed": nothing here is verified.

import type { Language } from "../api/types";

export const MOCK_LANGUAGES: Language[] = [
  { code: "en-IN", name: "English", native_name: "English", script: "Latn", font_family: "Noto Sans", prisma: "unconfirmed", timbre: "unconfirmed", command_keywords: false, demo: true, tested: false },
  { code: "ta-IN", name: "Tamil", native_name: "தமிழ்", script: "Taml", font_family: "Noto Sans Tamil", prisma: "unconfirmed", timbre: "unconfirmed", command_keywords: false, demo: true, tested: false },
  { code: "hi-IN", name: "Hindi", native_name: "हिन्दी", script: "Deva", font_family: "Noto Sans Devanagari", prisma: "unconfirmed", timbre: "unconfirmed", command_keywords: false, demo: true, tested: false },
];
