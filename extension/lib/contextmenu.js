import { ApiError } from "./api.js";
import { isLossless, qualityLabel } from "./format.js";
import { isLikelyVideoUrl } from "./links.js";

export const APP_NAME = "Ragazzo's Downloader";

// o menu só aparece nesses sites (links para eles ou páginas deles)
export const SITE_PATTERNS = [
  "*://*.youtube.com/*",
  "*://youtu.be/*",
  "*://*.tiktok.com/*",
  "*://*.instagram.com/*",
  "*://*.pinterest.com/*",
  "*://pin.it/*",
];

const GROUPS = [
  { id: "rd-link", contexts: ["link"], patterns: { targetUrlPatterns: SITE_PATTERNS } },
  { id: "rd-page", contexts: ["page", "video"], patterns: { documentUrlPatterns: SITE_PATTERNS } },
];

function choiceLabel(mode, choice) {
  const parts = [choice.ext.toUpperCase()];
  if (!isLossless(choice.ext)) parts.push(qualityLabel(mode, choice.quality));
  return parts.join(" · ");
}

export function menuItems(prefs) {
  const items = [];
  for (const group of GROUPS) {
    const common = { contexts: group.contexts, ...group.patterns };
    items.push({ id: group.id, title: APP_NAME, ...common });
    items.push({ id: `${group.id}-video`, parentId: group.id, title: `Baixar vídeo (${choiceLabel("video", prefs.video)})`, ...common });
    items.push({ id: `${group.id}-audio`, parentId: group.id, title: `Baixar áudio (${choiceLabel("audio", prefs.audio)})`, ...common });
  }
  return items;
}

export async function handleMenuClick(info, { prefs, api, badge }) {
  const id = String(info.menuItemId);
  const url = id.startsWith("rd-link") ? info.linkUrl : info.pageUrl;
  if (!url || !isLikelyVideoUrl(url)) {
    badge.error("Isso não parece um link de vídeo");
    return;
  }
  const mode = id.endsWith("-audio") ? "audio" : "video";
  const { quality, ext } = prefs[mode];
  try {
    const result = await api.addToQueue([url], mode, quality, ext);
    badge.ok(result.added.length ? "Adicionado à fila" : "Já estava na fila");
  } catch (error) {
    badge.error(error instanceof ApiError ? error.message : String(error));
  }
}
