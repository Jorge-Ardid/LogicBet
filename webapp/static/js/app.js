"use strict";
/* LogicBet Web — ядро: Header / Navigation / Матчі / Модалка ставки */

const state = { tab: "analytics", filter: "all", defaultStake: 10 };
const $ = (id) => document.getElementById(id);

async function api(path, opts) {
  const resp = await fetch(path, opts);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || "HTTP " + resp.status);
  return data;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

window.toast = function (msg, ok = true) {
  document.querySelectorAll(".toast").forEach((t) => t.remove());
  const el = document.createElement("div");
  el.className = "toast " + (ok ? "toast-ok" : "toast-err");
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2600);
};

/* HEADER: оновлюється лише текст банку — DOM шапки нерухомий */
async function loadState() {
  try {
    const st = await api("/api/state");
    $("bankroll-badge").textContent = st.bankroll.toFixed(1) + " грн";
    state.defaultStake = st.default_stake;
    const a = st.accuracy;
    $("accuracy-pct").textContent = "Точність " + a.pct.toFixed(1) + "%";
    $("accuracy-detail").textContent = "(" + a.hits + "/" + a.total + " успішних прогнозів)";
    return st;
  } catch (e) { /* офлайн */ }
}
window.loadState = loadState;

/* NAVIGATION: перемикання табів, fadeIn лише на тілі */
const NAV_ACTIVE = "bg-borderDark text-goldAccent font-semibold shadow-sm";
const NAV_IDLE = "text-gray-400 hover:text-gray-200";

function loadViewCurrent() {
  if (state.tab === "analytics") window.loadMatches();
  else if (state.tab === "history") window.loadHistory();
  else if (state.tab === "stats") window.loadStats();
}

function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.className = "nav-btn flex-1 min-w-[100px] py-2.5 rounded-lg text-center transition " +
      (btn.dataset.tab === tab ? NAV_ACTIVE : NAV_IDLE);
  });
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  const view = $("view-" + tab);
  view.classList.remove("hidden", "page-fade-in");
  void view.offsetWidth; /* перезапуск анімації */
  view.classList.add("page-fade-in");
  if (tab === "analytics") window.loadMatches();
  else if (tab === "history") window.loadHistory();
  else if (tab === "stats") window.loadStats();
  else if (tab === "settings") window.loadSettings();
}

/* АНАЛІТИКА: матчі, згруповані Сьогодні/Завтра */
let currentMatches = {};

function matchCardHtml(m) {
  const cls = m.status_key === "live" ? "text-goldAccent"
    : m.status_key === "finished" ? "text-red-400" : "text-green-400";
  const dot = m.status_key === "live" ? '<span class="live-dot mr-1"></span>' : "";
  const score = m.score ? '<span class="text-white font-extrabold ml-2">' + esc(m.score) + "</span>" : "";
  const prob = m.top_prob != null ? ' <span class="text-gray-400 font-normal">(' + m.top_prob + "%)</span>" : "";
  return '<div class="bg-cardBg border border-borderDark rounded-xl p-3.5 sm:p-4 hover:border-gray-700 transition space-y-3">' +
    '<div class="flex justify-between items-center text-xs border-b border-borderDark/60 pb-2">' +
      '<span class="font-bold uppercase tracking-wider ' + cls + '">' + dot + esc(m.status) + "</span>" +
      '<span class="text-gray-400">' + esc(m.league) + ' • <b class="text-gray-200">' + esc(m.time) + "</b></span>" +
    "</div>" +
    '<div class="flex flex-col md:flex-row justify-between md:items-center gap-3">' +
      '<div class="space-y-1 min-w-0">' +
        '<div class="text-base sm:text-lg font-bold text-white tracking-wide">' +
          esc(m.home) + ' <span class="text-gray-500 font-normal mx-1">—</span> ' + esc(m.away) + score +
        "</div>" +
        '<p class="text-xs sm:text-sm text-goldAccent font-medium leading-relaxed break-words">' +
          esc(m.summary || "Прогнози генеруються…") + prob +
        "</p>" +
      "</div>" +
      '<button class="bet-btn w-full sm:w-auto bg-borderDark hover:bg-goldAccent hover:text-black text-gray-200 font-bold px-5 py-2.5 rounded-lg border border-gray-700 transition text-xs sm:text-sm active:scale-95 shadow" data-id="' + m.id + '">СТАВКА</button>' +
    "</div></div>";
}
window.matchCardHtml = matchCardHtml;

async function loadMatches() {
  const box = $("matches-container");
  box.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
  try {
    const data = await api("/api/matches?filter=" + state.filter);
    currentMatches = {};
    (data.groups || []).forEach((g) => g.matches.forEach((m) => (currentMatches[m.id] = m)));
    const any = (data.groups || []).some((g) => g.matches.length);
    box.innerHTML = !any
      ? '<p class="text-gray-500 text-sm text-center py-8">На цю дату матчів немає 📭</p>'
      : data.groups.map((g) =>
          '<div class="space-y-3 pt-2">' +
            '<div class="flex items-center gap-2 border-b border-borderDark/60 pb-2">' +
              '<span class="text-base">📅</span>' +
              '<h2 class="text-goldAccent font-bold text-sm md:text-base tracking-wide uppercase">' +
                esc(g.title) +
                ' <span class="text-gray-400 font-normal text-xs md:text-sm lowercase ml-1">(' + esc(g.label) + ")</span>" +
              "</h2></div>" +
            (g.matches.map(matchCardHtml).join("") ||
              '<p class="text-gray-500 text-sm px-1">Немає матчів</p>') +
          "</div>").join("");
  } catch (e) {
    box.innerHTML = '<p class="text-red-400 text-sm text-center py-6">Помилка: ' + esc(e.message) + "</p>";
  }
}
/* МОДАЛЬНЕ ВІКНО СТАВКИ */
let modalMatch = null;

function openBetModal(m) {
  modalMatch = m;
  $("bm-match").textContent = m.home + " — " + m.away;
  $("bm-meta").textContent = m.league + " • " + m.time;
  const sel = $("bm-selection"), custom = $("bm-custom");
  sel.innerHTML =
    (m.predictions || []).map((p) =>
      '<option value="' + esc(p.selection) + '">' + esc(p.selection) + " (" + p.prob + "%)</option>").join("") +
    '<option value="__custom">✍️ Власний варіант…</option>';
  custom.classList.add("hidden");
  custom.value = "";
  sel.onchange = () => custom.classList.toggle("hidden", sel.value !== "__custom");
  $("bm-stake").value = state.defaultStake;
  const first = (m.predictions || [])[0];
  $("bm-odd").value = first && first.odd ? first.odd : "";
  $("bet-modal").classList.remove("hidden");
}

async function saveBet() {
  if (!modalMatch) return;
  const sel = $("bm-selection");
  const selection = sel.value === "__custom" ? $("bm-custom").value.trim() : sel.value;
  try {
    await api("/api/bets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        match_id: modalMatch.id,
        selection: selection,
        stake: parseFloat($("bm-stake").value),
        odd: parseFloat($("bm-odd").value),
      }),
    });
    toast("✅ Ставку прийнято!");
    $("bet-modal").classList.add("hidden");
    loadState();
  } catch (e) {
    toast("⚠️ " + e.message, false);
  }
}

/* ІНІЦІАЛІЗАЦІЯ */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".nav-btn").forEach((b) =>
    b.addEventListener("click", () => switchTab(b.dataset.tab)));

  const styleFilters = () => document.querySelectorAll(".filter-btn").forEach((b) => {
    b.className = "filter-btn px-3 py-1.5 rounded-md font-bold transition " +
      (b.dataset.filter === state.filter
        ? "bg-goldAccent text-black"
        : "bg-borderDark text-gray-300 hover:bg-gray-700");
  });
  document.querySelectorAll(".filter-btn").forEach((b) =>
    b.addEventListener("click", () => {
      state.filter = b.dataset.filter;
      styleFilters();
      loadMatches();
    }));
  styleFilters();

  $("btn-refresh").addEventListener("click", () => {
    const icon = $("refresh-icon");
    icon.classList.remove("spin");
    void icon.offsetWidth;
    icon.classList.add("spin");
    loadState();
    loadViewCurrent();
  });

  $("search-btn").addEventListener("click", () => window.doSearch && window.doSearch());
  $("search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && window.doSearch) window.doSearch();
  });

  $("bm-close").addEventListener("click", () => $("bet-modal").classList.add("hidden"));
  $("bet-modal").addEventListener("click", (e) => {
    if (e.target === $("bet-modal")) $("bet-modal").classList.add("hidden");
  });
  $("bm-save").addEventListener("click", saveBet);

  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".bet-btn");
    if (!btn) return;
    const m = currentMatches[btn.dataset.id] ||
      (window.currentSearchMatches && window.currentSearchMatches[btn.dataset.id]);
    if (m) openBetModal(m);
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }

  loadState();
  switchTab("analytics");
});