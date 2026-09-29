/** Pure helpers for the sign-in flow (no React, so they are easy to test). */

/**
 * Where to go after signing in. Only same-site paths are honoured, so a crafted
 * `/login?next=https://evil.example` link cannot bounce someone off-site.
 */
export function safeNext(value: string | null | undefined): string {
  if (!value) return "/";
  // Must be an absolute path on this origin. "//host" and "/\host" are treated
  // as protocol-relative URLs by browsers, so they are rejected.
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return "/";
  // Never send someone back to the sign-in page they just left.
  if (value === "/login" || value.startsWith("/login?") || value.startsWith("/login/")) return "/";
  // Control characters (e.g. an injected newline) are never legitimate in a path.
  if (/[\u0000-\u001f\u007f]/.test(value)) return "/";
  return value;
}
