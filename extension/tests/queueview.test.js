import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { createQueueView } from "../lib/queueview.js";

function setup() {
  const dom = new JSDOM(`<ul id="queue"></ul><p id="empty"></p><button id="clear" hidden></button><div id="update" hidden></div>`);
  const doc = dom.window.document;
  const calls = [];
  const view = createQueueView({
    list: doc.getElementById("queue"),
    empty: doc.getElementById("empty"),
    clearButton: doc.getElementById("clear"),
    updateBox: doc.getElementById("update"),
    actions: { cancel: (id) => calls.push(["cancel", id]), retry: (id) => calls.push(["retry", id]) },
  });
  return { doc, view, calls };
}

const item = (over = {}) => ({
  id: "a", url: "https://youtu.be/a", mode: "video", quality: "720", ext: "mp4", status: "downloading",
  title: "Vídeo A", progress: 0.1, speed: 2048, error_code: null, error_short: null, error_detail: null, ...over,
});

const button = (li, label) => [...li.querySelectorAll("button")].find((b) => b.textContent === label);

test("mostra os itens do mais novo para o mais antigo", () => {
  const { doc, view } = setup();
  view.render([item({ id: "a", title: "Primeiro" }), item({ id: "b", title: "Segundo" })]);
  const titles = [...doc.querySelectorAll(".item-title")].map((n) => n.textContent);
  assert.deepEqual(titles, ["Segundo", "Primeiro"]);
  assert.equal(doc.getElementById("empty").hidden, true);
});

test("atualizar o progresso não recria o botão Cancelar", () => {
  const { doc, view } = setup();
  view.render([item({ progress: 0.1 })]);
  const li = doc.querySelector("li");
  const cancel = button(li, "Cancelar");
  view.render([item({ progress: 0.5, speed: 4096 })]);
  assert.equal(doc.querySelector("li"), li);
  assert.equal(button(li, "Cancelar"), cancel);
  assert.match(li.querySelector(".item-meta").textContent, /50%/);
  assert.equal(li.querySelector(".fill").style.width, "50%");
});

test("clicar em Cancelar e em Tentar de novo chama a ação do item", () => {
  const { doc, view, calls } = setup();
  view.render([item()]);
  button(doc.querySelector("li"), "Cancelar").click();
  view.render([item({ status: "cancelled" })]);
  button(doc.querySelector("li"), "Tentar de novo").click();
  assert.deepEqual(calls, [["cancel", "a"], ["retry", "a"]]);
  assert.equal(button(doc.querySelector("li"), "Cancelar"), undefined);
});

test("detalhes abertos continuam no mesmo nó entre atualizações", () => {
  const { doc, view } = setup();
  const failed = item({ status: "error", error_code: "unknown", error_short: "Erro", error_detail: "pilha longa" });
  view.render([failed]);
  button(doc.querySelector("li"), "detalhes").click();
  const pre = doc.querySelector("pre.detail");
  assert.equal(pre.hidden, false);
  const textNode = pre.firstChild;
  view.render([{ ...failed, speed: null }]);
  assert.equal(doc.querySelector("pre.detail"), pre);
  assert.equal(pre.firstChild, textNode);  // seleção de texto não se perde
  button(doc.querySelector("li"), "ocultar detalhes").click();
  assert.equal(pre.hidden, true);
});

test("itens que saíram da fila somem e o vazio aparece", () => {
  const { doc, view } = setup();
  view.render([item()]);
  view.render([]);
  assert.equal(doc.querySelectorAll("li").length, 0);
  assert.equal(doc.getElementById("empty").hidden, false);
});

test("botão Limpar e aviso de atualização acompanham a fila", () => {
  const { doc, view } = setup();
  view.render([item()]);
  assert.equal(doc.getElementById("clear").hidden, true);
  view.render([item({ status: "error", error_code: "extractor", error_short: "O site mudou" })]);
  assert.equal(doc.getElementById("clear").hidden, false);
  assert.equal(doc.getElementById("update").hidden, false);
});
