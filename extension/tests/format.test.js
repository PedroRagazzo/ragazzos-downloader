import { test } from "node:test";
import assert from "node:assert/strict";
import { formatOptions, formatSpeed, isLossless, itemLabel, percent, qualityLabel, qualityOptions, statusLabel } from "../lib/format.js";

test("formatSpeed", () => {
  assert.equal(formatSpeed(0), "");
  assert.equal(formatSpeed(null), "");
  assert.equal(formatSpeed(2048), "2 KB/s");
  assert.equal(formatSpeed(1572864), "1,5 MB/s");
});

test("percent", () => {
  assert.equal(percent(0.456), "46%");
  assert.equal(percent(2), "100%");
  assert.equal(percent(undefined), "0%");
});

test("statusLabel", () => {
  assert.equal(statusLabel("converting"), "Convertendo");
  assert.equal(statusLabel("done"), "Concluído");
  assert.equal(statusLabel("estranho"), "estranho");
});

test("qualityOptions e qualityLabel", () => {
  assert.deepEqual(qualityOptions("video")[0], ["best", "Melhor"]);
  assert.deepEqual(qualityOptions("audio")[0], ["320", "320 kbps"]);
  assert.equal(qualityLabel("video", "720"), "720p");
  assert.equal(qualityLabel("audio", "192"), "192 kbps");
  assert.equal(qualityLabel("video", "999"), "999");
});

test("formatOptions por modo, padrão primeiro", () => {
  assert.deepEqual(formatOptions("video").map(([v]) => v), ["mp4", "mkv", "mov"]);
  assert.deepEqual(formatOptions("audio").map(([v]) => v), ["mp3", "wav", "flac"]);
});

test("isLossless só para WAV e FLAC", () => {
  assert.equal(isLossless("wav"), true);
  assert.equal(isLossless("flac"), true);
  assert.equal(isLossless("mp3"), false);
  assert.equal(isLossless("mkv"), false);
});

test("itemLabel mostra formato e qualidade", () => {
  assert.equal(itemLabel({ mode: "video", quality: "720", ext: "mkv" }), "🎬 MKV · 720p");
  assert.equal(itemLabel({ mode: "audio", quality: "192", ext: "mp3" }), "🎵 MP3 · 192 kbps");
  assert.equal(itemLabel({ mode: "audio", quality: "320", ext: "flac" }), "🎵 FLAC");
  assert.equal(itemLabel({ mode: "video", quality: "best" }), "🎬 MP4 · Melhor");
});
