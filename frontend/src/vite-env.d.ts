/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional base URL for the Open Guard API (empty = use the Vite dev proxy). */
  readonly VITE_API_BASE_URL?: string;
  /**
   * API key sent on protected (state-changing) requests so they pass the
   * backend auth layer. Leave unset only when the backend runs with auth
   * unconfigured (e.g. local dev with no OPEN_GUARD_API_KEYS).
   */
  readonly VITE_OPEN_GUARD_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
