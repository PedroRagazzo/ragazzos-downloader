import { formatOptions, qualityOptions } from "./format.js";

export const DEFAULT_PREFS = { mode: "video", quality: "best", ext: "mp4" };

function pick(options, value) {
  const values = options.map(([v]) => v);
  return values.includes(value) ? value : values[0];
}

export function normalizePrefs(raw) {
  const mode = raw?.mode === "audio" ? "audio" : "video";
  return {
    mode,
    quality: pick(qualityOptions(mode), raw?.quality),
    ext: pick(formatOptions(mode), raw?.ext),
  };
}

export async function loadPrefs(storage) {
  const { prefs } = await storage.get("prefs");
  return normalizePrefs(prefs);
}

export async function savePrefs(storage, prefs) {
  await storage.set({ prefs: normalizePrefs(prefs) });
}
