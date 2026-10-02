export const BASE = "http://127.0.0.1:47321";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  get offline() {
    return this.status === 0;
  }
}

async function request(method, path, body) {
  let response;
  try {
    response = await fetch(BASE + path, {
      method,
      // o programa só aceita pedidos com este cabeçalho (o Brave nem sempre manda Origin)
      headers: { "X-Video-Downloader": "1", ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Programa não está rodando", 0);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(data.error || `Erro ${response.status}`, response.status);
  return data;
}

export const api = {
  status: () => request("GET", "/status"),
  info: (url) => request("GET", `/info?url=${encodeURIComponent(url)}`),
  addToQueue: (urls, mode, quality) => request("POST", "/queue", { urls, mode, quality }),
  queue: () => request("GET", "/queue"),
  cancel: (id) => request("POST", `/queue/${encodeURIComponent(id)}/cancel`),
  retry: (id) => request("POST", `/queue/${encodeURIComponent(id)}/retry`),
  clearFinished: () => request("POST", "/queue/clear"),
  openFolder: () => request("POST", "/open-folder"),
  updateYtdlp: () => request("POST", "/update-ytdlp"),
};
