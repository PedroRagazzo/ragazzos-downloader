import { test } from "node:test";
import assert from "node:assert/strict";
import { detectSite, isLikelyVideoUrl, parseLinks } from "../lib/links.js";

test("parseLinks extrai links de texto do WhatsApp", () => {
  const text = "olha isso https://youtu.be/abc123!!\n\nbom dia\nhttps://www.tiktok.com/@a/video/123, https://youtu.be/abc123";
  assert.deepEqual(parseLinks(text), {
    urls: ["https://youtu.be/abc123", "https://www.tiktok.com/@a/video/123"],
    ignored: 1,
  });
});

test("parseLinks aceita CRLF, parênteses e ignora ftp", () => {
  const text = "(https://pin.it/abc)\r\nftp://arquivo\r\nhttps://www.instagram.com/reel/xyz/";
  assert.deepEqual(parseLinks(text), {
    urls: ["https://pin.it/abc", "https://www.instagram.com/reel/xyz/"],
    ignored: 1,
  });
});

test("parseLinks com texto vazio", () => {
  assert.deepEqual(parseLinks("  \n "), { urls: [], ignored: 0 });
});

test("detectSite reconhece domínios e links curtos", () => {
  assert.equal(detectSite("https://m.youtube.com/watch?v=x"), "youtube");
  assert.equal(detectSite("https://youtu.be/x"), "youtube");
  assert.equal(detectSite("https://vm.tiktok.com/ZM123/"), "tiktok");
  assert.equal(detectSite("https://www.instagram.com/reel/abc/"), "instagram");
  assert.equal(detectSite("https://br.pinterest.com/pin/123/"), "pinterest");
  assert.equal(detectSite("https://pin.it/abc"), "pinterest");
});

test("detectSite rejeita o resto", () => {
  assert.equal(detectSite("https://example.com"), null);
  assert.equal(detectSite("https://notyoutube.com/watch?v=x"), null);
  assert.equal(detectSite("chrome://extensions"), null);
  assert.equal(detectSite("não é url"), null);
});

test("isLikelyVideoUrl aceita páginas de vídeo", () => {
  for (const url of [
    "https://www.youtube.com/watch?v=abc",
    "https://www.youtube.com/shorts/abc",
    "https://youtu.be/abc",
    "https://www.tiktok.com/@a/video/123",
    "https://vm.tiktok.com/ZM123/",
    "https://www.instagram.com/reel/abc/",
    "https://www.instagram.com/p/abc/",
    "https://br.pinterest.com/pin/123/",
    "https://pin.it/abc",
  ]) {
    assert.equal(isLikelyVideoUrl(url), true, url);
  }
});

test("isLikelyVideoUrl recusa páginas que não são vídeo", () => {
  for (const url of [
    "https://www.youtube.com/",
    "https://www.youtube.com/@canal",
    "https://www.instagram.com/usuario/",
    "https://www.tiktok.com/@a",
    "https://example.com/video/1",
  ]) {
    assert.equal(isLikelyVideoUrl(url), false, url);
  }
});
