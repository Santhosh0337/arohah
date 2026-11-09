// Language helpers. The language list comes from GET /api/languages, which
// serves backend/data/languages.json. Nothing here changes a support status.

import type { Language } from "../api/types.ts";

/** Dev switch (VITE_ALLOW_UNVERIFIED_LANGUAGES=true). See docs/frontend.md. */
export function parseAllowUnverified(value: unknown): boolean {
  return String(value ?? "").trim().toLowerCase() === "true";
}

/**
 * A language can be chosen for lyrics only when Prisma is "confirmed" (bible
 * 16.2). With the dev switch on, unconfirmed ones are allowed too, and the UI
 * says so. "unsupported" is never selectable.
 */
export function isSelectable(lang: Language, allowUnverified: boolean): boolean {
  if (lang.prisma === "confirmed") return true;
  return allowUnverified && lang.prisma === "unconfirmed";
}

export function isVerified(lang: Language): boolean {
  return lang.prisma === "confirmed";
}

/** "hi-IN" -> "hi". Used for the HTML lang attribute. */
export function langAttr(code: string | null | undefined): string | undefined {
  if (!code) return undefined;
  return code.split("-")[0].toLowerCase() || undefined;
}

/** CSS font stack built from the font_family in languages.json. */
export function fontStack(lang: Pick<Language, "font_family"> | undefined): string {
  const first = lang?.font_family ? `"${lang.font_family}", ` : "";
  return `${first}"Noto Sans", system-ui, -apple-system, "Segoe UI", sans-serif`;
}

export function findLanguage(languages: Language[], code: string | null | undefined) {
  return code ? languages.find((l) => l.code === code) : undefined;
}

/** Unicode NFC, applied to user text before it is stored or compared. */
export function nfc(text: string): string {
  return text.normalize("NFC");
}
