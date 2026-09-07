/**
 * instrumentation.ts
 * ------------------
 * Runs once when the Next.js server process starts (stable instrumentation
 * hook, on by default since Next 15 -- no experimental flag needed).
 *
 * Works around a Node 22+ runtime quirk: Node now ships global
 * `localStorage`/`sessionStorage` objects (the Web Storage API), but without
 * `--localstorage-file` pointed at a real path, `localStorage` resolves to a
 * non-functional plain object (`{}`, not a real Storage instance -- no
 * getItem/setItem) instead of being `undefined`.
 *
 * Some browser-detection code -- including Next's own dev-overlay bundle,
 * which only ships in `next dev` -- uses `typeof localStorage !== 'undefined'`
 * as its "are we in a browser" check. That check now incorrectly passes
 * during SSR, and the very next line calling `localStorage.getItem(...)`
 * throws `TypeError: localStorage.getItem is not a function`, crashing
 * every page render in dev mode. Production is unaffected (Vercel's runtime
 * doesn't exhibit this, and the dev-overlay bundle isn't shipped in prod
 * builds), so this only matters for local development.
 *
 * Deleting the broken global (only if it's actually broken -- not a real
 * Storage instance) restores the correct "undefined" answer for that check.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  for (const key of ["localStorage", "sessionStorage"] as const) {
    const store = (globalThis as Record<string, unknown>)[key];
    if (store && typeof (store as { getItem?: unknown }).getItem !== "function") {
      delete (globalThis as Record<string, unknown>)[key];
    }
  }
}
