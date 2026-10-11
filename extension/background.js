// Service worker: menu do botão direito "Ragazzo's Downloader ▸ Baixar vídeo / Baixar áudio".
import { api } from "./lib/api.js";
import { createBadge } from "./lib/badge.js";
import { APP_NAME, handleMenuClick, menuItems } from "./lib/contextmenu.js";
import { loadPrefs } from "./lib/prefs.js";

const storage = chrome.storage.local;
const badge = createBadge(chrome.action, { defaultTitle: APP_NAME });

// recriações em fila: duas ao mesmo tempo dariam erro de id repetido no menu
let rebuilding = Promise.resolve();

function rebuildMenus() {
  rebuilding = rebuilding
    .then(async () => {
      await chrome.contextMenus.removeAll();
      const prefs = await loadPrefs(storage);
      for (const item of menuItems(prefs)) {
        chrome.contextMenus.create(item, () => void chrome.runtime.lastError);
      }
    })
    .catch((error) => console.error("não consegui montar o menu", error));
  return rebuilding;
}

chrome.runtime.onInstalled.addListener(() => rebuildMenus());
chrome.runtime.onStartup.addListener(() => rebuildMenus());
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.prefs) return rebuildMenus();  // títulos mostram o formato escolhido
});
chrome.contextMenus.onClicked.addListener(async (info) => {
  await handleMenuClick(info, { prefs: await loadPrefs(storage), api, badge });
});
