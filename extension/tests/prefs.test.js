import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPrefs, savePrefs } from "../lib/prefs.js";

function fakeStorage(initial = {}) {
  const data = { ...initial };
  return {
    data,
    async get(key) { return key in data ? { [key]: data[key] } : {}; },
    async set(obj) { Object.assign(data, obj); },
  };
}

test("sem nada salvo usa vídeo na melhor qualidade", async () => {
  assert.deepEqual(await loadPrefs(fakeStorage()), { mode: "video", quality: "best", ext: "mp4" });
});

test("carrega o que foi salvo", async () => {
  const storage = fakeStorage();
  await savePrefs(storage, { mode: "audio", quality: "192", ext: "flac" });
  assert.deepEqual(await loadPrefs(storage), { mode: "audio", quality: "192", ext: "flac" });
});

test("qualidade incompatível com o modo é corrigida", async () => {
  const storage = fakeStorage({ prefs: { mode: "audio", quality: "720" } });
  assert.deepEqual(await loadPrefs(storage), { mode: "audio", quality: "320", ext: "mp3" });
});

test("formato incompatível com o modo volta ao padrão", async () => {
  const storage = fakeStorage({ prefs: { mode: "video", quality: "720", ext: "flac" } });
  assert.deepEqual(await loadPrefs(storage), { mode: "video", quality: "720", ext: "mp4" });
});
