import { formatOptions, qualityOptions } from "./format.js";

// Guarda a última escolha de vídeo e a de áudio separadas: o popup volta a ela ao trocar de tipo
// e o menu do botão direito usa a de cada tipo.
const MODES = ["video", "audio"];

function pick(options, value) {
  const values = options.map(([v]) => v);
  return values.includes(value) ? value : values[0];
}

function normalizeChoice(mode, raw) {
  return { quality: pick(qualityOptions(mode), raw?.quality), ext: pick(formatOptions(mode), raw?.ext) };
}

export function normalizePrefs(raw) {
  const mode = raw?.mode === "audio" ? "audio" : "video";
  const prefs = { mode };
  for (const m of MODES) {
    // formato antigo: { mode, quality, ext } valia só para o tipo salvo
    const legacy = raw && !raw[m] && raw.mode === m ? { quality: raw.quality, ext: raw.ext } : null;
    prefs[m] = normalizeChoice(m, raw?.[m] ?? legacy);
  }
  return prefs;
}

export const DEFAULT_PREFS = normalizePrefs(null);

export function activeChoice(prefs) {
  return { mode: prefs.mode, ...prefs[prefs.mode] };
}

export function switchMode(prefs, mode) {
  return { ...prefs, mode: mode === "audio" ? "audio" : "video" };
}

export function updateChoice(prefs, patch) {
  return normalizePrefs({ ...prefs, [prefs.mode]: { ...prefs[prefs.mode], ...patch } });
}

export async function loadPrefs(storage) {
  const { prefs } = await storage.get("prefs");
  return normalizePrefs(prefs);
}

export async function savePrefs(storage, prefs) {
  await storage.set({ prefs: normalizePrefs(prefs) });
}
