/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  /** Dev only. "true" lets the form select languages whose Prisma status is unconfirmed. */
  readonly VITE_ALLOW_UNVERIFIED_LANGUAGES?: string;
}
