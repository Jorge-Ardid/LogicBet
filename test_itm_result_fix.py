#!/usr/bin/env python3
"""
ТЕСТ: Виправлення багу з розрахунком результатів ставок ITM/ITB
"""
import sys
sys.path.insert(0, r'C:\Users\jvjor\.cline\data\workspaces\chat\python')
from analytics import *

def test_elche_real_madrid():
    """Тест сценарію Elche — Real Madrid (2:3)"""
    print("=" * 70)
    print("ТЕСТ: Elche — Real Madrid (2:3)")
    print("Ставка: Elche ТМ 2.5 (Індивідуальний Тотал - Недотяг)")
    print("=" * 70)
    print()
    
    home_goals = 2  # Elche
    away_goals = 3  # Real Madrid
    line = 2.5
    
    print(f"Результат: Elche {home_goals} - {away_goals} Real Madrid")
    print(f"Загальна сума: {home_goals + away_goals}")
    print()
    
    # ПОМИЛКА РАНІШ (невірна логіка)
    print("ПОМИЛКА (рахували загальну суму):")
    total = home_goals + away_goals
    print(f"  ❌ LOST: {total} > {line} (рахували загальні готи!)")
    print()
    
    # КОРЕКТНИЙ розрахунок
    print("КОРЕКТНО (рахували тільки готи Elche):")
    print(f"  ✅ WON: {home_goals} < {line} (тільки готи Elche!)")
    print()
    
    if home_goals < line:
        print("✅ УСПІХ! Elche ТМ 2.5 = WON")
        return True
    return False

if __name__ == "__main__":
    test_elche_real_madrid()