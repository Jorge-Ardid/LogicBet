import os
import sqlite3
import sys

# Додаємо поточну папку в sys.path, щоб імпортувати модулі
sys.path.append(os.path.dirname(__file__))

from database import LogicBetDB
from analytics import BettingAnalytics
import main

def recalculate_all():
    print("=== ПОВНИЙ ПЕРЕРАХУНОК ELO ТА ФОРМИ ===")
    db = LogicBetDB()
    analytics = BettingAnalytics(db)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Скидаємо ELO для всіх команд
        print("1. Скидання рейтингу ELO всіх команд до базових 1500...")
        cursor.execute("UPDATE teams SET elo_rating = 1500.0, current_form = ''")
        
        # 2. Скидаємо статус обробки всіх матчів
        print("2. Скидання статусу обробки матчів...")
        cursor.execute("UPDATE matches SET elo_processed = 0, h_elo_change = 0.0, a_elo_change = 0.0")
        
        conn.commit()
    
    # 3. Викликаємо існуючу функцію з main.py для розрахунку ELO з нуля (в хронологічному порядку)
    print("3. Хронологічний перерахунок рейтингів (це може зайняти хвилину)...")
    main.recalculate_elo_from_history(db, analytics)
    
    print("\n✅ ПЕРЕРАХУНОК УСПІШНО ЗАВЕРШЕНО!")

if __name__ == "__main__":
    recalculate_all()
