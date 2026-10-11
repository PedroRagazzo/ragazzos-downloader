// Confirmação discreta no ícone da extensão (sem aviso do Windows): ✓ verde ou ! vermelho por alguns segundos.
const OK_MS = 4000;
const ERROR_MS = 8000;

export function createBadge(action, { schedule = setTimeout, cancel = clearTimeout, defaultTitle }) {
  let timer = null;

  function show(text, color, message, ms) {
    if (timer !== null) cancel(timer);
    action.setBadgeBackgroundColor({ color });
    action.setBadgeText({ text });
    action.setTitle({ title: `${defaultTitle} — ${message}` });
    timer = schedule(() => {
      timer = null;
      action.setBadgeText({ text: "" });
      action.setTitle({ title: defaultTitle });
    }, ms);
  }

  return {
    ok: (message) => show("✓", "#1f9d55", message, OK_MS),
    error: (message) => show("!", "#c62828", message, ERROR_MS),
  };
}
