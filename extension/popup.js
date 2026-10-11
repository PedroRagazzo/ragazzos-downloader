import { api, ApiError } from "./lib/api.js";
import { isLikelyVideoUrl, parseLinks } from "./lib/links.js";
import { formatOptions, isLossless, qualityOptions } from "./lib/format.js";
import { loadPrefs, savePrefs } from "./lib/prefs.js";
import { createQueueView } from "./lib/queueview.js";

const $ = (id) => document.getElementById(id);
const storage = chrome.storage.local;
let prefs = { mode: "video", quality: "best", ext: "mp4" };
let online = false;
let pageLoaded = false;

// ---- opções ----

function renderOptions() {
  for (const button of document.querySelectorAll("[data-mode]")) {
    const on = button.dataset.mode === prefs.mode;
    button.classList.toggle("active", on);
    button.setAttribute("aria-checked", String(on));
  }
  const format = $("format");
  format.replaceChildren(...formatOptions(prefs.mode).map(([value, label]) => new Option(label, value)));
  format.value = prefs.ext;
  const select = $("quality");
  select.replaceChildren(...qualityOptions(prefs.mode).map(([value, label]) => new Option(label, value)));
  select.value = prefs.quality;
  select.hidden = isLossless(prefs.ext);  // WAV/FLAC não têm kbps
}

async function setPrefs(next) {
  prefs = next;
  renderOptions();
  await savePrefs(storage, prefs);
}

for (const button of document.querySelectorAll("[data-mode]")) {
  button.addEventListener("click", () => {
    const mode = button.dataset.mode;
    if (mode !== prefs.mode) setPrefs({ mode, quality: qualityOptions(mode)[0][0], ext: formatOptions(mode)[0][0] });
  });
}
$("quality").addEventListener("change", (event) => setPrefs({ ...prefs, quality: event.target.value }));
$("format").addEventListener("change", (event) => setPrefs({ ...prefs, ext: event.target.value }));

// ---- conexão ----

function setOnline(isOnline, status) {
  online = isOnline;
  $("conn").classList.toggle("on", isOnline);
  $("conn-text").textContent = isOnline ? "Conectado" : "Desconectado";
  $("offline").hidden = isOnline;
  $("ffmpeg-warn").hidden = !isOnline || status?.ffmpeg !== false;
  $("page-add").disabled = !isOnline;
  $("links-add").disabled = !isOnline;
}

async function checkStatus() {
  try {
    setOnline(true, await api.status());
  } catch {
    setOnline(false);
  }
}

// ---- adicionar ----

async function addUrls(urls) {
  try {
    const result = await api.addToQueue(urls, prefs.mode, prefs.quality, prefs.ext);
    const parts = [];
    if (result.added.length) parts.push(`${result.added.length} adicionado(s)`);
    if (result.duplicates) parts.push(`${result.duplicates} já estava(m) na fila`);
    await refreshQueue();
    return { ok: true, text: parts.join(" · ") };
  } catch (error) {
    return { ok: false, text: error instanceof ApiError ? error.message : String(error) };
  }
}

$("links-add").addEventListener("click", async () => {
  const { urls, ignored } = parseLinks($("links").value);
  const notes = ignored ? [`${ignored} linha(s) ignorada(s)`] : [];
  if (!urls.length) {
    $("links-msg").textContent = [...notes, "nenhum link encontrado"].join(" · ");
    return;
  }
  const result = await addUrls(urls);
  if (result.ok) $("links").value = "";
  $("links-msg").textContent = [...notes, result.text].filter(Boolean).join(" · ");
});

async function loadPage() {
  if (pageLoaded || !online) return;
  pageLoaded = true;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab?.url;
  if (!url || !isLikelyVideoUrl(url)) return;

  $("page").hidden = false;
  $("page-title").textContent = tab.title || url;
  $("page-add").onclick = async () => {
    $("page-msg").textContent = (await addUrls([url])).text;
  };
  try {
    const info = await api.info(url);
    $("page-title").textContent = info.title;
    if (info.thumbnail) {
      const img = $("page-thumb");
      img.onerror = () => { img.hidden = true; };
      img.src = info.thumbnail;
      img.hidden = false;
    }
  } catch (error) {
    $("page-msg").textContent = error.message;
  }
}

// ---- fila ----

const queueView = createQueueView({
  list: $("queue"),
  empty: $("queue-empty"),
  clearButton: $("clear-finished"),
  updateBox: $("update-box"),
  actions: {
    cancel: (id) => api.cancel(id).then(refreshQueue, showOffline),
    retry: (id) => api.retry(id).then(refreshQueue, showOffline),
  },
});

function showOffline() {
  setOnline(false);
}

async function refreshQueue() {
  try {
    const { items } = await api.queue();
    if (!online) {
      await checkStatus();
      loadPage();
    }
    queueView.render(items);
  } catch {
    if (online) setOnline(false);
  }
}

// ---- botões gerais ----

$("open-folder").addEventListener("click", () => api.openFolder().catch(showOffline));
$("clear-finished").addEventListener("click", () => api.clearFinished().then(refreshQueue, showOffline));

$("update-btn").addEventListener("click", async () => {
  const button = $("update-btn");
  button.disabled = true;
  $("update-msg").textContent = "Atualizando… (pode levar 1 minuto)";
  try {
    const result = await api.updateYtdlp();
    $("update-msg").textContent = result.restarting
      ? `Atualizado para ${result.version}. Reiniciando o programa…`
      : `Já está na versão mais recente (${result.version}).`;
  } catch (error) {
    $("update-msg").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

// ---- início ----

async function init() {
  prefs = await loadPrefs(storage);
  renderOptions();
  await checkStatus();
  await refreshQueue();
  loadPage();
  setInterval(refreshQueue, 1000);
}

init();
