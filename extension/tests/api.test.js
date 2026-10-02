import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { api, ApiError, BASE } from "../lib/api.js";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

function mockFetch(handler) {
  const calls = [];
  globalThis.fetch = async (url, init) => { calls.push({ url, init }); return handler(url, init); };
  return calls;
}

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

test("addToQueue envia JSON por POST", async () => {
  const calls = mockFetch(() => json(200, { added: ["a"], duplicates: 0 }));
  const result = await api.addToQueue(["https://youtu.be/x"], "audio", "192");
  assert.deepEqual(result, { added: ["a"], duplicates: 0 });
  assert.equal(calls[0].url, `${BASE}/queue`);
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body), { urls: ["https://youtu.be/x"], mode: "audio", quality: "192" });
});

test("todo pedido leva o cabeçalho que identifica a extensão", async () => {
  const calls = mockFetch(() => json(200, { ok: true }));
  await api.status();
  await api.addToQueue(["https://youtu.be/x"], "video", "best");
  for (const call of calls) assert.equal(call.init.headers["X-Video-Downloader"], "1");
  assert.equal(calls[1].init.headers["Content-Type"], "application/json");
});

test("info codifica a URL", async () => {
  const calls = mockFetch(() => json(200, { title: "t" }));
  await api.info("https://youtu.be/x?a=1&b=2");
  assert.equal(calls[0].url, `${BASE}/info?url=${encodeURIComponent("https://youtu.be/x?a=1&b=2")}`);
});

test("erro do servidor vira ApiError com a mensagem", async () => {
  mockFetch(() => json(400, { error: "link inválido" }));
  await assert.rejects(api.queue(), (err) => err instanceof ApiError && err.message === "link inválido" && err.status === 400);
});

test("servidor desligado vira ApiError offline", async () => {
  mockFetch(() => { throw new TypeError("Failed to fetch"); });
  await assert.rejects(api.status(), (err) => err instanceof ApiError && err.offline && err.message === "Programa não está rodando");
});
