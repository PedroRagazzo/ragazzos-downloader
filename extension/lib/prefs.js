import { qualityOptions } from "./format.js";

export const DEFAULT_PREFS = { mode: "video", quality: "best" };

export function normalizePrefs(raw) {
  const mode = raw?.mode === "audio" ? "audio" : "video";
  const values = qualityOptions(mode).map(([value]) => value);
  const quality = values.includes(raw?.quality) ? raw.quality : values[0];
  return { mode, quality };
}

export async function loadPrefs(storage) {
  const { prefs } = await storage.get("prefs");
  return normalizePrefs(prefs);
}

export async function savePrefs(storage, prefs) {
  await storage.set({ prefs: normalizePrefs(prefs) });
}
