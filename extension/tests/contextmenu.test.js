import { test } from "node:test";
import assert from "node:assert/strict";
import { handleMenuClick, menuItems, SITE_PATTERNS } from "../lib/contextmenu.js";
import { createBadge } from "../lib/badge.js";
import { ApiError } from "../lib/api.js";

const PREFS = { mode: "video", video: { quality: "1080", ext: "mp4" }, audio: { quality: "320", ext: "flac" } };

test("menu tem um grupo para links e outro para a página, cada um com vídeo e áudio", () => {
  const items = menuItems(PREFS);
  const byId = Object.fromEntries(items.map((i) => [i.id, i]));
  assert.deepEqual(Object.keys(byId).sort(), ["rd-link", "rd-link-audio", "rd-link-video", "rd-page", "rd-page-audio", "rd-page-video"]);
  assert.equal(byId["rd-link"].title, "Ragazzo's Downloader");
  assert.equal(byId["rd-link-video"].title, "Baixar vídeo (MP4 · 1080p)");
  assert.equal(byId["rd-page-audio"].title, "Baixar áudio (FLAC)");
  assert.equal(byId["rd-link-audio"].parentId, "rd-link");
  for (const id of ["rd-link", "rd-link-video", "rd-link-audio"]) {
    assert.deepEqual(byId[id].contexts, ["link"]);
    assert.deepEqual(byId[id].targetUrlPatterns, SITE_PATTERNS);
  }
  for (const id of ["rd-page", "rd-page-video", "rd-page-audio"]) {
    assert.deepEqual(byId[id].contexts, ["page", "video"]);
    assert.deepEqual(byId[id].documentUrlPatterns, SITE_PATTERNS);
  }
});

test("só aparece nos sites suportados", () => {
  for (const site of ["youtube.com", "youtu.be", "tiktok.com", "instagram.com", "pinterest.com", "pin.it"]) {
    assert.ok(SITE_PATTERNS.some((p) => p.includes(site)), site);
  }
});

function fakeDeps({ result, error } = {}) {
  const calls = [];
  const badge = { ok: (msg) => calls.push(["ok", msg]), error: (msg) => calls.push(["error", msg]) };
  const api = {
    addToQueue: async (...args) => {
      calls.push(["add", ...args]);
      if (error) throw error;
      return result ?? { added: ["x"], duplicates: 0 };
    },
  };
  return { calls, deps: { prefs: PREFS, api, badge } };
}

test("clique num link usa o link clicado e a escolha de vídeo", async () => {
  const { calls, deps } = fakeDeps();
  await handleMenuClick({ menuItemId: "rd-link-video", linkUrl: "https://youtu.be/abc", pageUrl: "https://www.youtube.com/" }, deps);
  assert.deepEqual(calls, [["add", ["https://youtu.be/abc"], "video", "1080", "mp4"], ["ok", "Adicionado à fila"]]);
});

test("clique na página usa o endereço da página e a escolha de áudio", async () => {
  const { calls, deps } = fakeDeps();
  await handleMenuClick({ menuItemId: "rd-page-audio", pageUrl: "https://www.youtube.com/watch?v=abc" }, deps);
  assert.deepEqual(calls[0], ["add", ["https://www.youtube.com/watch?v=abc"], "audio", "320", "flac"]);
});

test("link que não é de vídeo não vai para a fila", async () => {
  const { calls, deps } = fakeDeps();
  await handleMenuClick({ menuItemId: "rd-link-video", linkUrl: "https://www.youtube.com/@canal" }, deps);
  assert.deepEqual(calls, [["error", "Isso não parece um link de vídeo"]]);
});

test("vídeo que já estava na fila avisa", async () => {
  const { calls, deps } = fakeDeps({ result: { added: [], duplicates: 1 } });
  await handleMenuClick({ menuItemId: "rd-page-video", pageUrl: "https://www.youtube.com/watch?v=abc" }, deps);
  assert.deepEqual(calls.at(-1), ["ok", "Já estava na fila"]);
});

test("programa fechado mostra o erro", async () => {
  const { calls, deps } = fakeDeps({ error: new ApiError("Programa não está rodando", 0) });
  await handleMenuClick({ menuItemId: "rd-page-video", pageUrl: "https://www.youtube.com/watch?v=abc" }, deps);
  assert.deepEqual(calls.at(-1), ["error", "Programa não está rodando"]);
});

function fakeAction() {
  const state = { text: "", color: null, title: null };
  const timers = [];
  const action = {
    setBadgeText: ({ text }) => { state.text = text; },
    setBadgeBackgroundColor: ({ color }) => { state.color = color; },
    setTitle: ({ title }) => { state.title = title; },
  };
  const schedule = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
  return { state, timers, action, schedule };
}

test("badge mostra ✓ verde e some depois", () => {
  const { state, timers, action, schedule } = fakeAction();
  const badge = createBadge(action, { schedule, cancel: () => {}, defaultTitle: "Ragazzo's Downloader" });
  badge.ok("Adicionado à fila");
  assert.equal(state.text, "✓");
  assert.equal(state.title, "Ragazzo's Downloader — Adicionado à fila");
  timers.at(-1).fn();
  assert.equal(state.text, "");
  assert.equal(state.title, "Ragazzo's Downloader");
});

test("badge mostra ! vermelho com o motivo no título", () => {
  const { state, action, schedule } = fakeAction();
  const badge = createBadge(action, { schedule, cancel: () => {}, defaultTitle: "Ragazzo's Downloader" });
  badge.error("Programa não está rodando");
  assert.equal(state.text, "!");
  assert.equal(state.title, "Ragazzo's Downloader — Programa não está rodando");
  assert.notEqual(state.color, null);
});
