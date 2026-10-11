import { before, test } from "node:test";
import assert from "node:assert/strict";

// chrome.* falso: guarda os listeners e o que foi criado no menu
const listeners = {};
const on = (name) => ({ addListener: (fn) => { listeners[name] = fn; } });
const menus = new Map();
const badge = { text: "", title: "" };
const stored = { prefs: { mode: "video", video: { quality: "720", ext: "mkv" }, audio: { quality: "192", ext: "mp3" } } };
const requests = [];

globalThis.chrome = {
  runtime: { onInstalled: on("installed"), onStartup: on("startup"), lastError: undefined },
  storage: {
    local: { get: async (k) => ({ [k]: stored[k] }) },
    onChanged: on("storageChanged"),
  },
  contextMenus: {
    removeAll: async () => { menus.clear(); },
    create: (item, cb) => { menus.set(item.id, item); cb?.(); },
    onClicked: on("clicked"),
  },
  action: {
    setBadgeText: ({ text }) => { badge.text = text; },
    setBadgeBackgroundColor: () => {},
    setTitle: ({ title }) => { badge.title = title; },
  },
};
globalThis.fetch = async (url, init) => {
  requests.push({ url, body: init.body ? JSON.parse(init.body) : null });
  return new Response(JSON.stringify({ added: ["x"], duplicates: 0 }), { status: 200 });
};

before(async () => {
  await import("../background.js");
});

test("ao instalar cria o menu com as escolhas salvas", async () => {
  await listeners.installed();
  assert.equal(menus.size, 6);
  assert.equal(menus.get("rd-page-video").title, "Baixar vídeo (MKV · 720p)");
});

test("mudar as preferências atualiza o menu", async () => {
  stored.prefs = { ...stored.prefs, audio: { quality: "320", ext: "wav" } };
  await listeners.storageChanged({ prefs: {} }, "local");
  assert.equal(menus.get("rd-link-audio").title, "Baixar áudio (WAV)");
});

test("clicar no menu manda o vídeo para o programa e mostra ✓", async () => {
  await listeners.clicked({ menuItemId: "rd-link-video", linkUrl: "https://youtu.be/abc" });
  assert.deepEqual(requests.at(-1).body, { urls: ["https://youtu.be/abc"], mode: "video", quality: "720", ext: "mkv" });
  assert.equal(badge.text, "✓");
});
