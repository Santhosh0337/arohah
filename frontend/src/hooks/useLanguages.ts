import { useEffect, useState } from "react";
import { getLanguages } from "../api/index.ts";
import { MOCK_LANGUAGES } from "../mocks/index.ts";
import type { Language } from "../api/types.ts";

export interface LanguagesState {
  languages: Language[];
  /** "api" = GET /api/languages. "bundled" = the fixture copy, used when the API is unreachable. */
  source: "loading" | "api" | "bundled";
  error: string | null;
}

/**
 * Loads the language list from GET /api/languages. If the API cannot be
 * reached it falls back to the bundled fixture copy (same data, same statuses)
 * and says so, so the form stays usable during frontend-only development.
 */
export function useLanguages(): LanguagesState {
  const [state, setState] = useState<LanguagesState>({ languages: [], source: "loading", error: null });

  useEffect(() => {
    let cancelled = false;
    getLanguages()
      .then((languages) => {
        if (!cancelled) setState({ languages, source: "api", error: null });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : "Could not load languages.";
        setState({ languages: MOCK_LANGUAGES, source: "bundled", error: message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
