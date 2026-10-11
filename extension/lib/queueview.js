import { formatSpeed, itemLabel, percent, statusLabel } from "./format.js";

const RUNNING = ["downloading", "converting"];
const ACTIVE = ["waiting", ...RUNNING];

// Atualiza a fila no lugar: só mexe no que mudou. Recriar tudo a cada segundo fazia o clique em
// "Cancelar" se perder e apagava a seleção de texto em "detalhes".
export function createQueueView({ list, empty, clearButton, updateBox, actions }) {
  const doc = list.ownerDocument;
  const nodes = new Map();  // id -> elementos do item
  const expanded = new Set();

  function el(tag, className) {
    const node = doc.createElement(tag);
    if (className) node.className = className;
    return node;
  }

  function setText(node, text) {
    if (node.textContent !== text) node.textContent = text;  // não troca o nó de texto à toa
  }

  function build(id) {
    const li = el("li", "item");
    const n = {
      li,
      title: el("div", "item-title"),
      meta: el("div", "item-meta"),
      bar: el("div", "bar"),
      fill: el("div", "fill"),
      error: el("div", "item-error"),
      toggle: el("button", "link"),
      detail: el("pre", "detail"),
      actions: el("div", "item-actions"),
      status: null,
    };
    n.bar.append(n.fill);
    n.toggle.type = "button";
    n.toggle.addEventListener("click", () => {
      if (expanded.has(id)) expanded.delete(id);
      else expanded.add(id);
      paintDetail(n, id);
    });
    li.append(n.title, n.meta, n.bar, n.error, n.toggle, n.detail, n.actions);
    return n;
  }

  function linkButton(label, onClick) {
    const button = el("button", "link");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  function paintDetail(n, id) {
    const open = expanded.has(id);
    setText(n.toggle, open ? "ocultar detalhes" : "detalhes");
    n.detail.hidden = !open;
  }

  function paint(n, item) {
    n.li.className = `item status-${item.status}`;
    setText(n.title, item.title || item.url);
    n.title.title = item.url;

    const bits = [itemLabel(item), statusLabel(item.status)];
    if (item.status === "downloading") {
      bits.push(percent(item.progress));
      const speed = formatSpeed(item.speed);
      if (speed) bits.push(speed);
    }
    setText(n.meta, bits.join(" · "));

    n.bar.hidden = !RUNNING.includes(item.status);
    n.fill.style.width = item.status === "converting" ? "100%" : percent(item.progress);

    const showError = Boolean(item.error_short) && item.status !== "done" && item.status !== "cancelled";
    n.error.hidden = !showError;
    setText(n.error, showError ? item.error_short : "");

    const hasDetail = item.status === "error" && Boolean(item.error_detail);
    n.toggle.hidden = !hasDetail;
    if (hasDetail) setText(n.detail, item.error_detail);
    else expanded.delete(item.id);
    paintDetail(n, item.id);

    if (n.status !== item.status) {  // botões só mudam quando o status muda
      n.status = item.status;
      const buttons = [];
      if (ACTIVE.includes(item.status)) buttons.push(linkButton("Cancelar", () => actions.cancel(item.id)));
      if (item.status === "error" || item.status === "cancelled") {
        buttons.push(linkButton("Tentar de novo", () => actions.retry(item.id)));
      }
      n.actions.replaceChildren(...buttons);
      n.actions.hidden = buttons.length === 0;
    }
  }

  function render(items) {
    const ids = new Set(items.map((i) => i.id));
    for (const [id, n] of nodes) {
      if (!ids.has(id)) {
        n.li.remove();
        nodes.delete(id);
        expanded.delete(id);
      }
    }
    [...items].reverse().forEach((item, index) => {
      let n = nodes.get(item.id);
      if (!n) {
        n = build(item.id);
        nodes.set(item.id, n);
      }
      paint(n, item);
      if (list.children[index] !== n.li) list.insertBefore(n.li, list.children[index] || null);
    });
    empty.hidden = items.length > 0;
    clearButton.hidden = !items.some((i) => !ACTIVE.includes(i.status));
    updateBox.hidden = !items.some((i) => i.status === "error" && i.error_code === "extractor");
  }

  return { render };
}
