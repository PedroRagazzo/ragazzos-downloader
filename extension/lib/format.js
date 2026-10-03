const STATUS_LABELS = {
  waiting: "Aguardando",
  downloading: "Baixando",
  converting: "Convertendo",
  done: "Concluído",
  error: "Erro",
  cancelled: "Cancelado",
};

const QUALITY_OPTIONS = {
  video: [["best", "Melhor"], ["1080", "1080p"], ["720", "720p"], ["480", "480p"], ["360", "360p"]],
  audio: [["320", "320 kbps"], ["192", "192 kbps"], ["128", "128 kbps"]],
};

const FORMAT_OPTIONS = {
  video: [["mp4", "MP4"], ["mkv", "MKV"], ["mov", "MOV"]],
  audio: [["mp3", "MP3"], ["wav", "WAV"], ["flac", "FLAC"]],
};

export function formatOptions(mode) {
  return FORMAT_OPTIONS[mode === "audio" ? "audio" : "video"];
}

// WAV e FLAC não têm kbps: a qualidade não se aplica
export function isLossless(ext) {
  return ext === "wav" || ext === "flac";
}

export function itemLabel(item) {
  const ext = item.ext || formatOptions(item.mode)[0][0];
  const parts = [`${item.mode === "audio" ? "🎵" : "🎬"} ${ext.toUpperCase()}`];
  if (!isLossless(ext)) parts.push(qualityLabel(item.mode, item.quality));
  return parts.join(" · ");
}

export function formatSpeed(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec <= 0) return "";
  if (bytesPerSec >= 1024 * 1024) return `${(bytesPerSec / (1024 * 1024)).toFixed(1).replace(".", ",")} MB/s`;
  return `${Math.round(bytesPerSec / 1024)} KB/s`;
}

export function percent(progress) {
  const p = Math.min(Math.max(Number(progress) || 0, 0), 1);
  return `${Math.round(p * 100)}%`;
}

export function statusLabel(status) {
  return STATUS_LABELS[status] ?? status;
}

export function qualityOptions(mode) {
  return QUALITY_OPTIONS[mode === "audio" ? "audio" : "video"];
}

export function qualityLabel(mode, quality) {
  const found = qualityOptions(mode).find(([value]) => value === quality);
  return found ? found[1] : quality;
}
