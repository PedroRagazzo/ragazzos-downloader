import { test } from "node:test";
import assert from "node:assert/strict";
import { activeChoice, loadPrefs, savePrefs, switchMode, updateChoice } from "../lib/prefs.js";

function fakeStorage(initial = {}) {
  const data = { ...initial };
  return {
    data,
    async get(key) { return key in data ? { [key]: data[key] } : {}; },
    async set(obj) { Object.assign(data, obj); },
  };
}

const DEFAULTS = { mode: "video", video: { quality: "best", ext: "mp4" }, audio: { quality: "320", ext: "mp3" } };

test("sem nada salvo usa os padrões de vídeo e de áudio", async () => {
  assert.deepEqual(await loadPrefs(fakeStorage()), DEFAULTS);
});

test("guarda vídeo e áudio separados", async () => {
  const storage = fakeStorage();
  const prefs = { mode: "audio", video: { quality: "720", ext: "mkv" }, audio: { quality: "192", ext: "flac" } };
  await savePrefs(storage, prefs);
  assert.deepEqual(await loadPrefs(storage), prefs);
});

test("preferência salva no formato antigo vira a escolha daquele tipo", async () => {
  const storage = fakeStorage({ prefs: { mode: "audio", quality: "192", ext: "flac" } });
  assert.deepEqual(await loadPrefs(storage), { ...DEFAULTS, mode: "audio", audio: { quality: "192", ext: "flac" } });
});

test("qualidade ou formato incompatíveis com o tipo voltam ao padrão", async () => {
  const storage = fakeStorage({ prefs: { mode: "video", video: { quality: "320", ext: "flac" }, audio: { quality: "720", ext: "mkv" } } });
  assert.deepEqual(await loadPrefs(storage), DEFAULTS);
});

test("activeChoice devolve a escolha do tipo atual", () => {
  const prefs = { ...DEFAULTS, mode: "audio", audio: { quality: "128", ext: "mp3" } };
  assert.deepEqual(activeChoice(prefs), { mode: "audio", quality: "128", ext: "mp3" });
});

test("trocar de tipo mantém a última escolha de cada um", () => {
  const prefs = { mode: "video", video: { quality: "720", ext: "mkv" }, audio: { quality: "192", ext: "wav" } };
  const audio = switchMode(prefs, "audio");
  assert.deepEqual(activeChoice(audio), { mode: "audio", quality: "192", ext: "wav" });
  assert.deepEqual(activeChoice(switchMode(audio, "video")), { mode: "video", quality: "720", ext: "mkv" });
});

test("updateChoice muda só o tipo atual", () => {
  const next = updateChoice(DEFAULTS, { ext: "mov" });
  assert.deepEqual(next.video, { quality: "best", ext: "mov" });
  assert.deepEqual(next.audio, DEFAULTS.audio);
});
