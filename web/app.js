// The page shows the register's answer without changing it (L4). Every piece of API text goes in with
// textContent, never as HTML markup: model and register text are data (threat T-W1).
import { LABELS } from "./i18n.js";

let lang = "en";
const $ = (id) => document.getElementById(id);
const t = (k) => LABELS[lang][k] ?? LABELS.en[k];

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c === null || c === undefined || c === "") continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

function setLang(next) {
  lang = next;
  document.documentElement.lang = next;
  for (const node of document.querySelectorAll("[data-t]")) node.textContent = t(node.dataset.t);
  for (const node of document.querySelectorAll("[data-tp]")) node.placeholder = t(node.dataset.tp);
  for (const b of document.querySelectorAll("[data-lang]")) b.setAttribute("aria-pressed", String(b.dataset.lang === next));
  try { localStorage.setItem("lang", next); } catch { /* storage may be blocked */ }
}

function showTab(name) {
  for (const which of ["ask", "check"]) {
    $(`tab-${which}`).setAttribute("aria-selected", String(which === name));
    $(`panel-${which}`).hidden = which !== name;
  }
}

async function api(path, body) {
  const init = body === undefined ? {} : {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  };
  const response = await fetch(path, init);
  let data = null;
  try { data = await response.json(); } catch { /* not JSON */ }
  return { status: response.status, data };
}

function notice(text, kind = "info") {
  $("result").replaceChildren(el("p", { class: `notice ${kind}` }, text));
}

function rowCard(use) {
  const fields = [
    ["crop", use.crop_raw], ["pest", use.pest_raw], ["dose_ai", use.dose_ai_raw],
    ["dose_form", use.dose_form_raw], ["dilution", use.dilution_raw], ["wait", use.wait_raw],
  ];
  const list = el("dl");
  for (const [k, v] of fields) list.append(el("dt", {}, t(k)), el("dd", {}, v || "—"));
  const c = use.citation;
  const pages = c.page_first === c.page_last ? c.page_first : `${c.page_first}–${c.page_last}`;
  const link = el("a", { href: c.url, target: "_blank", rel: "noopener" }, t("open_pdf"));
  return el("article", { class: "row" }, el("h4", {}, use.product_heading), list,
    el("p", { class: "cite" }, `${t("page")} ${pages} · ${c.document_id} · `, link));
}

function answerCard(headline, message, answer, clarification) {
  const out = [];
  if (clarification) {
    out.push(el("h3", {}, t("clarify")), el("p", { class: "message" }, clarification.question));
    $("result").replaceChildren(...out);
    $("question").focus();
    return;
  }
  if (answer && answer.restrictions && answer.restrictions.length) {
    const box = el("div", { class: "warning", role: "alert" }, el("strong", {}, t("restriction")));
    for (const r of answer.restrictions) box.append(el("p", {}, `${r.ingredient}: ${r.detail_raw} (${t("page")} ${r.page})`));
    out.push(box);
  }
  const approved = answer && answer.outcome === "APPROVED";
  out.push(el("h3", { class: approved ? "headline yes" : "headline no" }, headline));
  if (message && message !== headline) out.push(el("p", { class: "message" }, message));
  if (answer) {
    if (answer.uses.length) {
      out.push(el("h4", {}, `${t("rows")} (${t("as_printed")})`));
      for (const use of answer.uses.slice(0, 10)) out.push(rowCard(use));
    }
    if (answer.alternatives.length) {
      out.push(el("h4", {}, t("instead")));
      for (const use of answer.alternatives.slice(0, 5)) out.push(rowCard(use));
    }
    const suggestions = Object.values(answer.suggestions || {}).flat();
    if (suggestions.length) out.push(el("p", {}, `${t("suggest")}: ${suggestions.map((s) => s.display).join(", ")}`));
    out.push(el("p", { class: "disclaimer" }, answer.disclaimer));
  }
  $("result").replaceChildren(...out);
}

async function ask(event) {
  event.preventDefault();
  const question = $("question").value.trim();
  if (!question) return;
  notice(t("working"));
  const { status, data } = await api("/v1/ask", { question }).catch(() => ({ status: 0, data: null }));
  if (status === 200 && data) return answerCard(data.headline, data.message, data.answer, data.clarification);
  if (status === 503) { notice(t("unavailable"), "warn"); return showTab("check"); }
  if (status === 429) return notice(t("limited"), "warn");
  notice(t("error"), "warn");
}

async function check(event) {
  event.preventDefault();
  const body = { product: $("product").value.trim(), crop: $("crop").value.trim() };
  const pest = $("pest").value.trim();
  if (pest) body.pest = pest;
  notice(t("working"));
  const { status, data } = await api("/v1/lookup", body).catch(() => ({ status: 0, data: null }));
  if (status === 200 && data) return answerCard(data.headline, "", data, null);
  if (status === 429) return notice(t("limited"), "warn");
  notice(t("error"), "warn");
}

function suggest(input, list, path, label) {
  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) return;
    timer = setTimeout(async () => {
      const extra = path === "/v1/pests" && $("crop").value.trim() ? `&crop=${encodeURIComponent($("crop").value.trim())}` : "";
      const { status, data } = await api(`${path}?q=${encodeURIComponent(q)}${extra}`).catch(() => ({ status: 0 }));
      if (status !== 200 || !Array.isArray(data)) return;
      $(list).replaceChildren(...data.map((d) => el("option", { value: d[label] })));
    }, 250);
  });
}

async function registerDate() {
  const { status, data } = await api("/v1/register").catch(() => ({ status: 0 }));
  if (status !== 200 || !data) return;
  const dates = [...new Set(Object.values(data.dates))].join(", ");
  $("register-date").textContent = `${t("register_date")}: ${dates}`;
}

document.addEventListener("DOMContentLoaded", () => {
  let saved = "en";
  try { saved = localStorage.getItem("lang") || "en"; } catch { /* storage may be blocked */ }
  setLang(LABELS[saved] ? saved : "en");
  for (const b of document.querySelectorAll("[data-lang]")) b.addEventListener("click", () => { setLang(b.dataset.lang); registerDate(); });
  $("tab-ask").addEventListener("click", () => showTab("ask"));
  $("tab-check").addEventListener("click", () => showTab("check"));
  $("ask-form").addEventListener("submit", ask);
  $("check-form").addEventListener("submit", check);
  suggest($("product"), "product-list", "/v1/products", "heading");
  suggest($("crop"), "crop-list", "/v1/crops", "display");
  suggest($("pest"), "pest-list", "/v1/pests", "display");
  registerDate();
});
