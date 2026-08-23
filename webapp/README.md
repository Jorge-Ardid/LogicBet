# LogicBet Web

Веб-версія LogicBet (Flask) на базі існуючої аналітики `python/database.py`.
Єдина БД — `godot_app/logicbet.db` (та сама, яку оновлює CI-синхронізація).
Локальні дані (`user_bets`, `config`/банкрол) живуть на сервері і ніколи не
перезаписуються веб-додатком.

## Запуск

```
cd webapp
run.bat            (або: python app.py)
```

Сайт: http://localhost:8000 — відкрийте з телефона у тій же Wi-Fi мережі
(`http://<IP-комп'ютера>:8000`), далі «Додати на головний екран» → PWA.

## Структура

| Модуль | Файл | Роль |
|---|---|---|
| Header | `templates/index.html` | шапка з банком — нерухома |
| Navigation | `templates/index.html` | таби — нерухомі |
| Main Content | `static/js/app.js`, `static/js/views.js` | перемальовується через Fetch/AJAX |
| Footer | `templates/index.html` | підвал |

API: `/api/state`, `/api/matches?filter=all|today|tomorrow`, `/api/bets`
(GET/POST/DELETE), `/api/stats`, `/api/search?q=`, `/api/settings`.

PWA: `static/manifest.json` + `static/sw.js` + іконки.
