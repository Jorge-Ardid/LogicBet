import sqlite3
import os

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../godot_app/logicbet.db'))
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute('''
    SELECT market, selection, is_hit, bookmaker_odd 
    FROM predictions 
    WHERE is_hit IS NOT NULL
''')
predictions = c.fetchall()

total_invested = 0
total_profit = 0
won = 0
lost = 0
skipped = 0

market_stats = {}

for m, sel, hit, odd in predictions:
    if odd is None or odd <= 1.0:
        # If no real odds, assume a default average odd just to see theoretical ROI
        odd = 1.85
        
    total_invested += 1
    
    if m not in market_stats:
        market_stats[m] = {'invested': 0, 'profit': 0, 'won': 0, 'lost': 0}
        
    market_stats[m]['invested'] += 1
    
    if hit == 1:
        won += 1
        profit = (odd - 1.0)
        total_profit += profit
        market_stats[m]['won'] += 1
        market_stats[m]['profit'] += profit
    else:
        lost += 1
        total_profit -= 1.0
        market_stats[m]['lost'] += 1
        market_stats[m]['profit'] -= 1.0

print("=== РОЗРАХУНОК ROI (RETURN ON INVESTMENT) ===")
print(f"Всього оцінено прогнозів: {total_invested}")

if total_invested > 0:
    print(f"Виграно: {won}")
    print(f"Програно: {lost}")
    print(f"Win Rate (точність): {(won/total_invested)*100:.1f}%")
    print(f"Сума інвестицій (1 unit на ставку): {total_invested} units")
    print(f"Чистий прибуток: {total_profit:.2f} units")
    print(f"Загальний ROI: {(total_profit / total_invested)*100:.2f}%\n")
    
    print("--- ROI за маркетами ---")
    for m, stats in market_stats.items():
        inv = stats['invested']
        prof = stats['profit']
        w = stats['won']
        print(f"Маркет: {m}")
        print(f"  Ставок: {inv}")
        print(f"  Win Rate: {(w/inv)*100:.1f}%")
        print(f"  Прибуток: {prof:.2f} units")
        print(f"  ROI: {(prof/inv)*100:.2f}%")
        print()
else:
    print("Не знайдено розрахованих прогнозів для аналізу.")
