"use strict";
// !!! ПРИМУСОВА ВЕРСІЯ V15 — індикатор перезавантаження кешу !!!

/* LogicBet Web — вкладки: Історія / Пошук / Статистика / Налаштування */

/* ---------- ІСТОРІЯ СТАВОК (з пагінацією «Показати ще») ---------- */
const H_ACTIVE = "bg-goldAccent text-black";
const H_IDLE = "bg-borderDark text-gray-300 hover:bg-gray-700";
let hStatus = "ALL";
let hOffset = 0;
const H_PAGE_LIMIT = 300;

function betBadge(s) {
  if (s === "WON") return "bg-greenAccent/15 text-greenAccent border-greenAccent/40";
  if (s === "LOST") return "bg-red-500/10 text-red-400 border-red-500/40";
  return "bg-goldAccent/10 text-goldAccent border-goldAccent/40";
}


function historyCard(b) {
  const label = { WON: "WON ✓", LOST: "LOST ✗", PENDING: "PENDING ⏳" };
  const bet = b.bet;
  const hasBet = bet && bet.status;
  const statusKey = hasBet ? bet.status : null;
  const badgeClass = hasBet ? betBadge(statusKey) : "bg-gray-600 text-gray-300 border-gray-600";
  const statusLabel = hasBet ? (label[statusKey] || statusKey) : "БЕЗ СТАВКИ";

  /* --- КЛІКАБЕЛЬНІСТЬ ІСТОРІЇ ---
     Назви команд -> «Профіль команди» (window.teamModal), рахунок ->
     «Деталі матчу» (window.matchModal). Використовуємо ТІ САМІ класи
     .team-link / .detail-btn, що й картки матчів: глобальне делегування
     кліків в app.js вже обслуговує їх на всій сторінці.
     Курсор/ховер: cursor-pointer + underline/goldAccent-ефекти. */
  const _parts = (b.home != null && b.away != null)
    ? [b.home, b.away]
    : String(b.match || "").split(" — ");
  const teamBtn = (name, tid) =>
    '<button class="team-link hover:underline underline-offset-4 decoration-2 cursor-pointer transition text-left"' +
    ' data-tid="' + esc(tid != null ? String(tid) : "") + '" title="Профіль команди">' +
    esc(name) + "</button>";
  const matchLine =
    '<p class="font-bold text-white text-sm flex flex-wrap items-center gap-x-0.5">' +
      teamBtn(_parts[0] || "", b.home_id) +
      '<button class="detail-btn text-gray-500 mx-1 hover:text-goldAccent cursor-pointer transition" data-mid="' + esc(String(b.id)) + '" title="Аналіз матчу">—</button>' +
      teamBtn(_parts[1] || "", b.away_id) +
      (b.score
        ? ('<button class="detail-btn font-extrabold ml-1 hover:text-goldAccent cursor-pointer transition" data-mid="' + esc(String(b.id)) + '" title="Повна статистика матчу">' +
           '<span class="text-goldAccent">' + esc(b.score) + "</span></button>")
        : "") +
    "</p>";

  return '<div class="bg-cardBg border border-borderDark rounded-xl p-3.5 space-y-2">' +
    '<div class="flex justify-between items-center text-xs">' +
      '<span class="px-2 py-1 rounded-md border font-bold ' + badgeClass + '">' + esc(statusLabel) + "</span>" +
      '<span class="text-gray-400">' + esc(b.league) + " • " + esc(b.time) + "</span>" +
    "</div>" +
    matchLine +
    (hasBet
      ? ('<p class="text-xs text-goldAccent break-words">' + esc(bet.selection) + "</p>" +
         '<div class="flex justify-between text-xs text-gray-400">' +
           "<span>Ставка: <b class='text-gray-200'>" + bet.stake.toFixed(1) + " грн</b> • Кф: <b class='text-gray-200'>" +
           bet.odd.toFixed(2) + "</b></span>" +
           '<span class="' + (bet.profit > 0 ? "text-greenAccent" : bet.profit < 0 ? "text-red-400" : "text-gray-400") + ' font-bold">' + (bet.profit > 0 ? "+" : "") + bet.profit.toFixed(2) + " грн</span>" +
         "</div>")
      : '<p class="text-xs text-gray-500 italic">Ставка не зроблена</p>'
    ) +
    "</div>";
}


window.loadHistory = async function (silent) {
  const box = $("history-container");
  if (hOffset === 0 && !silent) box.innerHTML = '<div class="skeleton"></div>';
  try {
    const data = await api("/api/bets?status=" + hStatus +
                           "&limit=" + H_PAGE_LIMIT + "&offset=" + hOffset);
    const items = data.bets || [];

    if (!items.length && hOffset === 0) {
      box.innerHTML = '<p class="text-gray-500 text-sm text-center py-8">Ставок ще немає 🎯</p>';
      return;
    }
    const html = items.map(historyCard).join("");
    if (hOffset === 0) {
      box.innerHTML = '<div id="hist-list" class="space-y-3">' + html + "</div>";
    } else {
      $("hist-list").insertAdjacentHTML("beforeend", html);
    }

    /* Довантаження старіших записів (23.08, 22.08, …) — наступним offset,
       без перезапису поточного списку. */
    let more = $("load-more-wrap");
    if (!more) {
      more = document.createElement("div");
      more.id = "load-more-wrap";
      more.className = "py-3";
      box.appendChild(more);
    }
    more.innerHTML = "";
    const indicator = document.createElement("p");
    indicator.className = "text-center text-xs text-gray-500 py-2";
    indicator.textContent = data.has_more
      ? "--- ВЕРСІЯ V15 (ПОВНА ІСТОРІЯ) ---"
      : "--- Всі записи завантажені ---";
    more.appendChild(indicator);

    if (data.has_more) {
      const left = Math.max((data.total || 0) - data.next_offset, 0);
      const btn = document.createElement("button");
      btn.id = "btn-load-more";
      btn.className = "w-full bg-borderDark hover:bg-gray-700 text-gray-300 font-bold py-2 rounded-lg text-sm transition active:scale-95";
      btn.textContent = "ЗАВАНТАЖИТИ ЩЕ" + (left ? " (" + left + ")" : "");
      btn.addEventListener("click", function () {
        this.disabled = true;
        this.textContent = "Завантаження…";
        hOffset = data.next_offset;
        window.loadHistory(true);
      });
      more.appendChild(btn);
    }
  } catch (e) {
    box.innerHTML = '<p class="text-red-400 text-sm text-center py-6">Помилка: ' + esc(e.message) + "</p>";
  }
};

document.querySelectorAll(".hbtn").forEach((b) =>
  b.addEventListener("click", () => {
    hStatus = b.dataset.bstatus;
    hOffset = 0; /* новий фільтр — з початку історії */
    document.querySelectorAll(".hbtn").forEach((x) => {
      x.className = "hbtn px-3 py-1.5 rounded-md font-bold transition " +
        (x.dataset.bstatus === hStatus ? H_ACTIVE : H_IDLE);
    });
    window.loadHistory();
  }));

/* ---------- ПОШУК ---------- */
window.currentSearchMatches = {};

window.doSearch = async function () {
  const q = $("search-input").value.trim();
  const box = $("search-container");
  if (q.length < 2) {
    box.innerHTML = '<p class="text-gray-500 text-sm">Введіть мінімум 2 символи</p>';
    return;
  }
  box.innerHTML = '<div class="skeleton"></div>';
  try {
    const data = await api("/api/search?q=" + encodeURIComponent(q));
    window.currentSearchMatches = {};
    (data.matches || []).forEach((m) => { window.currentSearchMatches[m.id] = m; });
    box.innerHTML = !data.matches.length
      ? '<p class="text-gray-500 text-sm text-center py-6">Нічого не знайдено за «' + esc(q) + "»</p>"
      : data.matches.map(window.matchCardHtml).join("");
  } catch (e) {
    box.innerHTML = '<p class="text-red-400 text-sm text-center py-6">Помилка: ' + esc(e.message) + "</p>";
  }
};

/* ---------- СТАТИСТИКА ---------- */
window.loadStats = async function () {
  const cards = $("stats-cards");
  const mk = $("stats-markets");
  try {
    const s = await api("/api/stats");
    const card = (label, value, cls) =>
      '<div class="bg-cardBg border border-borderDark rounded-xl p-3.5 text-center">' +
        '<p class="text-gray-400 text-[11px] uppercase tracking-wide font-medium">' + label + "</p>" +
        '<p class="' + cls + ' font-extrabold text-lg md:text-xl mt-1">' + value + "</p></div>";
    cards.innerHTML =
      card("Банкрол", s.bankroll.toFixed(1) + " грн", "text-greenAccent") +
      card("ВІНРЕЙТ", s.winrate_pct + "%", "text-goldAccent") +
      card("В / П / В", s.bets.won + "/" + s.bets.lost + "/" + s.bets.pending, "text-white") +
      card("Прибуток", (s.profit > 0 ? "+" : "") + s.profit.toFixed(2) + " грн",
        s.profit >= 0 ? "text-greenAccent" : "text-red-400") +
      '<div class="col-span-2 md:col-span-4">' +
        card("Точність моделі", s.model_accuracy.pct + "% (" +
          s.model_accuracy.hits + "/" + s.model_accuracy.total + ")", "text-goldAccent") +
      "</div>";
    mk.innerHTML = !s.by_market.length ? "" :
      '<h3 class="text-gray-400 text-xs uppercase font-bold tracking-wide pt-1">Точність по маркетах</h3>' +
      s.by_market.map((m) => {
        const pct = m.total ? Math.round(m.hits * 100 / m.total) : 0;
        return '<div class="bg-cardBg border border-borderDark rounded-lg px-3 py-2 flex items-center justify-between text-xs">' +
          '<span class="text-gray-300 font-medium">' + esc(window.uaMarket ? window.uaMarket(m.market) : m.market) + "</span>" +
          '<span class="flex items-center gap-2">' +
            '<span class="w-24 h-1.5 bg-borderDark rounded-full overflow-hidden">' +
              '<span class="block h-full bg-goldAccent" style="width:' + pct + '%"></span></span>' +
            '<b class="text-goldAccent">' + pct + "%</b> " +
            "<span class='text-gray-500'>(" + m.hits + "/" + m.total + ")</span></span></div>";
      }).join("");
  } catch (e) {
    cards.innerHTML = '<p class="text-red-400 text-sm text-center py-6 col-span-4">Помилка: ' + esc(e.message) + "</p>";
  }
};

/* ---------- НАЛАШТУВАННЯ ---------- */
window.loadSettings = async function () {
  try {
    const s = await api("/api/settings");
    $("set-bankroll").value = s.bankroll;
    $("set-stake").value = s.default_stake;
  } catch (e) {
    window.toast("⚠️ " + e.message, false);
  }
};

$("settings-save").addEventListener("click", async () => {
  try {
    await api("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bankroll: parseFloat($("set-bankroll").value),
        default_stake: parseFloat($("set-stake").value),
      }),
    });
    window.toast("✅ Збережено!");
    window.loadState();
  } catch (e) {
    window.toast("⚠️ " + e.message, false);
  }
});