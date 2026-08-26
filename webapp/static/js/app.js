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

/* Локалізація назв маркетів (розділ «Статистика» та будь-які UI-відображення).
   Сервер віддає канонічні англійські ключі таблиці predictions.market —
   тут вони перетворюються на українські підписи; невідоме повертається як є. */
const MARKET_UA = {
  "Individual Total": "Індивідуальний тотал",
  "BTTS": "Обидві заб'ють (ОЗ)",
  "Total Goals": "Тотал голів",
  "1X2/DC": "Результат / Подвійний шанс",
  "Cards": "Картки",
  "1st Half Goals": "Голи в 1-му таймі",
  "Corners": "Кутові"
};
window.uaMarket = function (name) {
  const key = String(name ?? "").trim();
  return MARKET_UA[key] || name;
};

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
    /* Загальний баланс (включно із замороженими під PENDING портфелем) */
    $("bankroll-badge").textContent = st.balance_total.toFixed(1) + " грн";
    state.defaultStake = st.default_stake;
    /* Доступні кошти (Free Capital) */
    const freeEl = $("bal-free-badge");
    if (freeEl) freeEl.textContent = "🪙 " + st.free_capital.toFixed(1);
    /* Settled ROI % — ефективність лише за розрахованими ставками */
    const roiEl = $("roi-badge");
    if (roiEl) {
      const r = st.settled_roi_pct;
      const colorCls = r == null ? "text-goldAccent"
        : r > 0 ? "text-greenAccent border-greenAccent/40"
        : r < 0 ? "text-red-400 border-red-500/40" : "text-goldAccent";
      roiEl.className = "hidden sm:block bg-cardBg border font-bold text-xs sm:text-sm px-2 py-1.5 rounded-lg whitespace-nowrap " + colorCls;
      roiEl.textContent = r == null ? "ROI —"
        : "ROI " + (r > 0 ? "+" : "") + r.toFixed(1) + "%";
    }
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

/* Фаворит за АКТУАЛЬНИМ Elo: команда з вищим Elo — зелений, друга —
   нейтральний сірий (щоб аутсайдер не виглядав "у кризі"). Якщо Elo нема
   або вони рівні — стандартний білий. */
const ELO_GREEN = "#22c55e";
const ELO_GRAY = "#9ca3af";
function teamNameByElo(name, hElo, aElo, home) {
  const h = Number(hElo || 0), a = Number(aElo || 0);
  let color = null;
  if (h && a && h !== a) color = (home === (h > a)) ? ELO_GREEN : ELO_GRAY;
  return color
    ? '<span style="color:' + color + '">' + esc(name) + "</span>"
    : esc(name);
}
function matchCardHtml(m) {
  /* Зелений — ВИКЛЮЧНО для LIVE. ОЧІКУЄТЬСЯ — нейтральний сірий,
     завершені — червонуваті. */
  const cls = m.status_key === "live" ? "text-greenAccent"
    : m.status_key === "finished" ? "text-red-400" : "text-gray-300";
  const dot = m.status_key === "live" ? '<span class="live-dot mr-1"></span>' : "";
  const score = m.score
    ? '<button class="detail-btn text-white font-extrabold ml-1 hover:text-goldAccent cursor-pointer transition" data-mid="' + m.id + '" title="Аналіз матчу">' + esc(m.score) + "</button>"
    : "";
  const prob = m.top_prob != null ? ' <span class="text-gray-400 font-normal">(' + m.top_prob + "%)</span>" : "";
  const betLabel = m.has_bet && m.bet_odd != null
    ? Number(m.bet_odd).toFixed(2)
    : "СТАВКА";
  const betBtnCls = m.has_bet
    ? "bg-borderDark hover:bg-gray-700 text-gray-300 border-gray-500/50"
    : "bg-goldAccent/10 hover:bg-goldAccent hover:text-black text-goldAccent border-goldAccent/60";
  return '<div class="bg-cardBg border border-borderDark rounded-xl p-3.5 sm:p-4 hover:border-gray-700 transition space-y-3">' +
    '<div class="flex justify-between items-center text-xs border-b border-borderDark/60 pb-2">' +
      '<span class="font-bold uppercase tracking-wider ' + cls + '">' + dot + esc(m.status) + "</span>" +
      '<span class="text-gray-400">' + esc(m.league) + ' • <b class="text-gray-200">' + esc(m.time) + "</b></span>" +
    "</div>" +
    '<div class="flex flex-col md:flex-row justify-between md:items-center gap-3">' +
      '<div class="space-y-1 min-w-0">' +
        '<div class="text-base sm:text-lg font-bold text-white tracking-wide flex flex-wrap items-center gap-x-0.5">' +
          '<button class="team-link hover:underline underline-offset-4 decoration-2 cursor-pointer transition text-left" data-tid="' + m.home_id + '" title="Профіль команди">' + teamNameByElo(m.home, m.home_elo, m.away_elo, true) + "</button>" +
          '<button class="detail-btn text-gray-500 font-normal mx-1.5 hover:text-goldAccent cursor-pointer transition" data-mid="' + m.id + '" title="Аналіз матчу / порівняння">—</button>' +
          '<button class="team-link hover:underline underline-offset-4 decoration-2 cursor-pointer transition text-left" data-tid="' + m.away_id + '" title="Профіль команди">' + teamNameByElo(m.away, m.home_elo, m.away_elo, false) + "</button>" +
          score +
        "</div>" +
        '<p class="text-xs sm:text-sm text-goldAccent font-medium leading-relaxed break-words">' +
          esc(m.summary || "Прогнози генеруються…") + prob +
        "</p>" +
      "</div>" +
      '<button class="bet-btn w-full sm:w-auto ' + betBtnCls + ' font-bold px-5 py-2.5 rounded-lg border transition text-xs sm:text-sm active:scale-95 shadow" data-id="' + m.id + '">' + betLabel + '</button>' +
    "</div></div>";
}
window.matchCardHtml = matchCardHtml;

async function loadMatches(silent) {
  const box = $("matches-container");
  if (!silent) box.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
  try {
    const data = await api("/api/matches?filter=" + state.filter);
    currentMatches = {};
    (data.groups || []).forEach((g) => g.matches.forEach((m) => {
      // резервне сортування за Confidence Score спаданням (якщо серверне не спрацювало)
      if (m.predictions && Array.isArray(m.predictions)) {
        m.predictions.sort((a, b) => (b.confidence_score_pct || 0) - (a.confidence_score_pct || 0));
      }
      currentMatches[m.id] = m;
    }));
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
/* СТАВКА тепер на окремій сторінці /bet/<match_id> — перехід у клік-обробнику нижче */

/* ===== МОДАЛЬНІ ВІКНА: Аналіз матчу / Порівняння / Профіль команди ===== */
function closeModal() {
  const m = $("lb-modal");
  if (m) m.remove();
}

function openModal(innerHtml) {
  closeModal();
  const ov = document.createElement("div");
  ov.id = "lb-modal";
  ov.className = "fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-3";
  ov.innerHTML =
    '<div class="bg-cardBg border border-borderDark rounded-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto p-4 sm:p-5 space-y-3 shadow-2xl">' +
      '<button id="modal-close" class="float-right text-gray-400 hover:text-white text-2xl leading-none -mt-1 px-1">×</button>' +
      innerHtml +
    "</div>";
  document.body.appendChild(ov);
  ov.addEventListener("click", (e) => {
    if (e.target === ov || e.target.id === "modal-close") closeModal();
  });
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

function modalHeader(title) {
  return '<h3 class="font-bold text-goldAccent uppercase tracking-wide text-sm">' + esc(title) + "</h3>";
}

function formChips(letters) {
  const cls = { W: "bg-greenAccent/15 text-greenAccent border-greenAccent/40",
                D: "bg-gray-500/15 text-gray-300 border-gray-500/40",
                L: "bg-red-500/10 text-red-400 border-red-500/40" };
  return (letters || []).map((l) =>
    '<span class="inline-flex w-6 h-6 items-center justify-center rounded-md border text-[11px] font-extrabold ' +
    (cls[l] || cls.D) + '">' + l + "</span>").join(" ") ||
    '<span class="text-gray-500 text-xs">немає даних</span>';
}

/* Симетричний рядок статистики: h — господарі, a — гості */
function statRow(label, h, a, suffix) {
  suffix = suffix || "";
  const total = (Number(h) || 0) + (Number(a) || 0);
  const pctH = total ? Math.round((Number(h) || 0) * 100 / total) : 50;
  return (
    '<div class="space-y-1">' +
      '<div class="flex justify-between text-xs font-bold">' +
        '<span class="text-white">' + (h ?? "—") + suffix + "</span>" +
        '<span class="text-gray-400 uppercase tracking-wide text-[10px] pt-0.5">' + esc(label) + "</span>" +
        '<span class="text-white">' + (a ?? "—") + suffix + "</span>" +
      "</div>" +
      '<div class="flex h-1.5 rounded-full overflow-hidden bg-borderDark">' +
        '<span class="h-full bg-goldAccent" style="width:' + pctH + '%"></span>' +
        '<span class="h-full bg-gray-600 flex-1"></span>' +
      "</div>" +
    "</div>");
}

window.matchModal = async function (mid) {
  openModal('<p class="text-gray-400 text-sm py-8 text-center animate-pulse">Завантаження…</p>');
  try {
    const d = await api("/api/match/" + mid + "/details");
    let html = modalHeader(d.league + " • " + d.status + " • " + d.time);
    html +=
      '<div class="flex justify-between items-center gap-2">' +
        '<b class="text-sm sm:text-base text-white">' + esc(d.home.name) + "</b>" +
        (d.score
          ? '<span class="font-extrabold text-xl text-goldAccent whitespace-nowrap">' + esc(d.score[0]) + ":" + esc(d.score[1]) +
            (d.ht ? ' <small class="text-gray-500 font-normal text-xs">(' + d.ht[0] + ":" + d.ht[1] + ")</small>" : "") + "</span>"
          : '<span class="text-gray-500 font-normal text-xs">VS</span>') +
        '<b class="text-sm sm:text-base text-white">' + esc(d.away.name) + "</b>" +
      "</div>";

    if (d.stats) {
      html += '<div class="space-y-2.5 pt-1">' +
        statRow("Володіння %", d.stats.possession[0], d.stats.possession[1]) +
        statRow("xG", d.stats.xg[0], d.stats.xg[1]) +
        statRow("Удари", d.stats.shots_total[0], d.stats.shots_total[1]) +
        statRow("Удари в ціль", d.stats.shots_on[0], d.stats.shots_on[1]) +
        statRow("Удари повз", d.stats.shots_off[0], d.stats.shots_off[1]) +
        statRow("Кутові", d.stats.corners[0], d.stats.corners[1]) +
        statRow("Жовті картки", d.stats.yellow[0], d.stats.yellow[1]) +
        statRow("Червоні картки", d.stats.red[0], d.stats.red[1]) +
        "</div>";
      if (d.elo_change) {
        const fmt = (v) => (v > 0 ? "+" : "") + v;
        html += '<p class="text-xs text-center text-gray-400 pt-1">ΔElo: ' +
          '<b class="' + (d.elo_change[0] >= 0 ? "text-greenAccent" : "text-red-400") + '">' + fmt(d.elo_change[0]) + "</b> / " +
          '<b class="' + (d.elo_change[1] >= 0 ? "text-greenAccent" : "text-red-400") + '">' + fmt(d.elo_change[1]) + "</b></p>";
      }
    } else if (d.comparison) {
      const H = d.comparison.home, A = d.comparison.away;
      const line = (label, hv, av, suf) =>
        '<div class="flex justify-between text-xs py-1 border-b border-borderDark/50">' +
          '<b class="text-white">' + (hv ?? "—") + (suf || "") + "</b>" +
          '<span class="text-gray-400 uppercase tracking-wide text-[10px] pt-0.5">' + esc(label) + "</span>" +
          '<b class="text-white">' + (av ?? "—") + (suf || "") + "</b></div>";
      /* Контекстний венюний Elo (Зміна A): господар показує свій HOME-канал,
         гість — AWAY-канал; загальний середній лишається маленьким довідником. */
      const hCtx = (H.home_elo != null) ? H.home_elo : H.elo;
      const aCtx = (A.away_elo != null) ? A.away_elo : A.elo;
      html += '<div class="grid grid-cols-2 gap-3 text-center">' +
          '<div><p class="text-[11px] text-gray-500 uppercase">🏠 Home Elo</p>' +
            '<p class="font-extrabold text-lg text-white">' + hCtx + '</p>' +
            '<p class="text-[10px] text-gray-500">загальний ' + H.elo + '</p>' +
            '<div class="mt-1 flex justify-center">' + formChips(H.form_letters) + "</div></div>" +
          '<div><p class="text-[11px] text-gray-500 uppercase">✈️ Away Elo</p>' +
            '<p class="font-extrabold text-lg text-white">' + aCtx + '</p>' +
            '<p class="text-[10px] text-gray-500">загальний ' + A.elo + '</p>' +
            '<div class="mt-1 flex justify-center">' + formChips(A.form_letters) + "</div></div>" +
        "</div>";
      html += '<div class="pt-1">' +
        line("Сер. кутові", H.avg.corners, A.avg.corners) +
        line("Сер. ЖК", H.avg.yellow_cards, A.avg.yellow_cards) +
        line("Сер. ЧК", H.avg.red_cards, A.avg.red_cards) +
        line("Сер. xG", H.avg.xg, A.avg.xg) +
        "</div>" +
        '<p class="text-[11px] text-gray-500 text-center">Порівняння команд до матчу • вибірка ' + Math.max(H.avg.sample, A.avg.sample) + " матчів</p>";
    } else {
      html += '<p class="text-gray-500 text-sm text-center py-4">Статистика ще недоступна</p>';
    }
    openModal(html);
  } catch (e) {
    openModal('<p class="text-red-400 text-sm py-6 text-center">Помилка: ' + esc(e.message) + "</p>");
  }
};

window.teamModal = async function (tid) {
  openModal('<p class="text-gray-400 text-sm py-8 text-center animate-pulse">Завантаження…</p>');
  try {
    const t = await api("/api/team/" + tid + "/profile");
    let html = modalHeader("Профіль команди");
    /* Деталізація роздільного Elo (Зміна A): Загальний / Вдома 🏠 / На виїзді ✈️ */
    const fmtElo = (v) => Number(v).toFixed(1);
    const hasVenue = t.home_elo != null && t.away_elo != null;
    const venueBadges =
      (hasVenue
        ? '<span class="bg-greenAccent/10 border border-greenAccent/30 text-greenAccent font-bold px-1.5 py-1 rounded-md text-[11px] whitespace-nowrap" title="Домашній Elo">🏠 ' + fmtElo(t.home_elo) + "</span>" +
          '<span class="bg-borderDark border border-gray-500/40 text-gray-300 font-bold px-1.5 py-1 rounded-md text-[11px] whitespace-nowrap" title="Виїзний Elo">✈️ ' + fmtElo(t.away_elo) + "</span>"
        : "");
    html += '<div class="flex items-center justify-between gap-2 flex-wrap">' +
        '<b class="text-lg text-white">' + esc(t.name) + "</b>" +
        '<span class="flex items-center gap-1.5 flex-wrap justify-end">' +
          '<span class="bg-goldAccent/10 border border-goldAccent/40 text-goldAccent font-extrabold px-2.5 py-1 rounded-lg text-sm" title="Загальний Elo">Elo ' + t.elo + "</span>" +
          venueBadges +
        "</span>" +
      "</div>";
    const meta = [];
    if (t.rank) meta.push("№" + t.rank);
    if (t.points) meta.push(t.points + " очок");
    if (meta.length) html += '<p class="text-xs text-gray-400">' + meta.join(" • ") + "</p>";

    html += '<div class="space-y-1">' +
        '<p class="text-[11px] text-gray-500 uppercase tracking-wide">Форма (останні ' + (t.form_letters.length || 0) + ')</p>' +
        '<div>' + formChips(t.form_letters) + "</div>" +
      "</div>";

    const avgLine = (label, v, suf) =>
      '<div class="flex justify-between text-xs py-1 border-b border-borderDark/50">' +
        '<span class="text-gray-400">' + label + "</span>" +
        '<b class="text-white">' + (v ?? "—") + (suf || "") + "</b></div>";
    html += '<div class="pt-1">' +
      avgLine("Середні кутові", t.avg.corners) +
      avgLine("Середні ЖК", t.avg.yellow_cards) +
      avgLine("Середні ЧК", t.avg.red_cards) +
      avgLine("Середній xG", t.avg.xg) +
      "</div>" +
      '<p class="text-[11px] text-gray-500">Вибірка: останні ' + t.avg.sample + ' матчів зі статистикою</p>';

    if (t.recent && t.recent.length) {
      const rc = { W: "text-greenAccent", D: "text-gray-300", L: "text-red-400" };
      html += '<div><p class="text-[11px] text-gray-500 uppercase tracking-wide pb-1">Останні матчі</p>' +
        '<div class="space-y-1">' +
        t.recent.map((m) =>
          '<div class="flex items-center gap-2 text-xs">' +
            '<b class="' + (rc[m.r] || "") + ' w-4 text-center">' + m.r + "</b>" +
            '<span class="text-gray-300 flex-1 truncate">' + (m.venue === "H" ? "" : "@ ") + esc(m.opp) + "</span>" +
            '<span class="text-gray-400">' + m.score + '</span>' +
            '<span class="text-gray-600">' + esc(m.date) + "</span>" +
          "</div>").join("") + "</div></div>";
    }
    if (t.next) {
      html += '<p class="text-xs text-center pt-1">Наступний: <b class="text-goldAccent">' +
        (t.next.venue === "H" ? " вдома" : " виїзд") + " vs " + esc(t.next.opp) + "</b> " +
        '<span class="text-gray-500">(' + esc(t.next.date) + ")</span></p>";
    }
    openModal(html);
  } catch (e) {
    openModal('<p class="text-red-400 text-sm py-6 text-center">Помилка: ' + esc(e.message) + "</p>");
  }
};

/* Делегування: клік по назві команди / рахунку / розділювачу */
document.addEventListener("click", (e) => {
  const tl = e.target.closest(".team-link");
  if (tl && tl.dataset.tid) { window.teamModal(+tl.dataset.tid); return; }
  const dbtn = e.target.closest(".detail-btn");
  if (dbtn && dbtn.dataset.mid) { window.matchModal(+dbtn.dataset.mid); return; }
});

/* ===== АВТО-ФОНОВЕ ОНОВЛЕННЯ ДАНИХ =====
   Свіжість без перезавантаження: повторний fetch активного погляду
   при таймері (~30с) і при поверненні фокусу/вкладки (visibilitychange).
   /api/* обробляється SW як Network-Only та no-cache Flask-заголовками,
   тож тут завжди приходять свіжі дані (статуси матчів, Історія). */
let autoRefreshTimer = null;
function refreshActiveView(silent) {
  if (state.tab === "history") { window.loadHistory(silent); }
  else if (state.tab === "analytics") { window.loadMatches(silent); }
}
function startAutoRefresh() {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer);
  autoRefreshTimer = setInterval(() => refreshActiveView(true), 30000);
}
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.tab &&
      (state.tab === "history" || state.tab === "analytics")) {
    refreshActiveView(true);  // повернулись на вкладку — одразу свіжі дані
  }
});
window.addEventListener("focus", () => {
  if (state.tab === "history" || state.tab === "analytics") refreshActiveView(true);
});

/* ІНІЦІАЛІЗАЦІЯ */
document.addEventListener("DOMContentLoaded", () => {
  /* повернення зі сторінки ставки: підтвердження */
  if (new URLSearchParams(location.search).get("saved")) {
    toast("✅ Ставку прийнято!");
    history.replaceState(null, "", "/");
  }

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

  /* СТАВКА = перехід на окрему сторінку ставки */
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".bet-btn");
    if (!btn) return;
    location.href = "/bet/" + btn.dataset.id;
  });

    /* SW update: миттєва перезавантаження при виході нової версії */
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").then((reg) => {
      reg.addEventListener("updatefound", () => {
        const newW = reg.installing;
        if (newW) newW.addEventListener("statechange", () => {
          if (newW.state === "installed" && navigator.serviceWorker.controller) {
            location.reload(); // нова SW активна — перезавантажуємо
          }
        });
      });
    }).catch(() => {});
    navigator.serviceWorker.addEventListener("message", (event) => {
      if (event.data && event.data.type === "SW_UPDATED") {
        location.reload();
      }
    });
  }

  loadState();
  switchTab("analytics");
  startAutoRefresh();
});