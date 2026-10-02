const SITE_PATTERNS = [
  ["youtube", /(^|\.)(youtube\.com|youtu\.be)$/],
  ["tiktok", /(^|\.)tiktok\.com$/],
  ["instagram", /(^|\.)instagram\.com$/],
  ["pinterest", /(^|\.)(pinterest\.[a-z.]+|pin\.it)$/],
];

function parseUrl(url) {
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u : null;
  } catch {
    return null;
  }
}

export function detectSite(url) {
  const u = parseUrl(url);
  if (!u) return null;
  const host = u.hostname.toLowerCase();
  for (const [site, pattern] of SITE_PATTERNS) {
    if (pattern.test(host)) return site;
  }
  return null;
}

export function isLikelyVideoUrl(url) {
  const site = detectSite(url);
  if (!site) return false;
  const u = new URL(url);
  const host = u.hostname.toLowerCase();
  const path = u.pathname;
  switch (site) {
    case "youtube":
      if (host === "youtu.be") return path.length > 1;
      return (path === "/watch" && u.searchParams.has("v")) || /^\/(shorts|live)\/[^/]+/.test(path);
    case "tiktok":
      return /^(vm|vt)\./.test(host) || /\/video\/\d+/.test(path);
    case "instagram":
      return /^\/(reels?|p|tv)\/[^/]+/.test(path) || /^\/[^/]+\/(reel|p)\/[^/]+/.test(path);
    case "pinterest":
      return host === "pin.it" || /^\/pin\/[^/]+/.test(path);
  }
  return false;
}

// caracteres invisíveis (U+200B–U+200F, U+FEFF) e o ponto japonês "。" encerram o link
const URL_IN_TEXT = /https?:\/\/[^\s<>"'​-‏﻿。]+/gi;
// * e ~ são as marcas de negrito/tachado do WhatsApp; _ não entra porque aparece em IDs de vídeo
const TRAILING_PUNCTUATION = /[.,;:!?)\]}»"'…*~]+$/;

export function parseLinks(text) {
  const urls = [];
  const seen = new Set();
  let ignored = 0;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    const found = line.match(URL_IN_TEXT);
    if (!found) {
      ignored++;
      continue;
    }
    for (const candidate of found) {
      const url = candidate.replace(TRAILING_PUNCTUATION, "");
      if (!parseUrl(url) || seen.has(url)) continue;
      seen.add(url);
      urls.push(url);
    }
  }
  return { urls, ignored };
}
