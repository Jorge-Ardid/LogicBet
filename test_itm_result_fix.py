#!/usr/bin/env python3
"""
ТЕСТ: Перевірка виправлення багу з розрахунком ITM/ITB
Тестуємо конкретні матчі зі скаргою
"""
import sys
sys.path.insert(0, r'C:\Users\jvjor\.cline\data\workspaces\chat\python')
from analytics import check_market_result, MarketType

def main():
    print("=" * 70)
    print("ТЕСТ: Перевірка конкретних матчів")
    print("=" * 70)
    print()
    
    all_passed = True
    line = 2.5
    
    # Матч 1: Elche 2 - 3 Real Madrid
    # Ставка: Elche ТМ 2.5 (Elche - домашня команда)
    print("МАТЧ 1: Elche 2 - 3 Real Madrid")
    print("-" * 70)
    home1, away1 = 2, 3
    
    result1, explanation1 = check_market_result(
        MarketType.ITM,  # Или MarketType.ITM для домашньої команди
        home_goals=home1,
        away_goals=away1,
        is_home_team=True,  # Elche - домашня
        line=line
    )
    
    print(f"Результат матчу: Elche {home1} - {away1} Real Madrid")
    print(f"Ставка: Elche ТМ {line} (Індивідуальний тотал - Недотяг)")
    print(f"Розрахунок: {result1}")
    print(f"Пояснення: {explanation1}")
    print()
    
    if result1 == "WON":
        print("✅ УСПІХ! Elche ТМ 2.5 = WON")
    else:
        print("❌ ПОМИЛКА! Elche ТМ 2.5 має бути WON!")
        all_passed = False
    print()
    
    # Матч 2: Rayo Vallecano 2 - 1 Espanyol
    # Ставка: Espanyol ТМ 2.5 (Espanyol - гостра команда)
    print("МАТЧ 2: Rayo Vallecano 2 - 1 Espanyol")
    print("-" * 70)
    home2, away2 = 2, 1
    
    result2, explanation2 = check_market_result(
        MarketType.ITM2,  # Или MarketType.ITM2 для гострої команди
        home_goals=home2,
        away_goals=away2,
        is_home_team=False,  # Espanyol - гостра
        line=line
    )
    
    print(f"Результат матчу: Rayo Vallecano {home2} - {away2} Espanyol")
    print(f"Ставка: Espanyol ТМ {line} (Індивідуальний тотал - Недотяг)")
    print(f"Розрахунок: {result2}")
    print(f"Пояснення: {explanation2}")
    print()
    
    if result2 == "WON":
        print("✅ УСПІХ! Espanyol ТМ 2.5 = WON")
    else:
        print("❌ ПОМИЛКА! Espanyol ТМ 2.5 має бути WON!")
        all_passed = False
    print()
    
    # Підсумок
    print("=" * 70)
    print("ПІДСУМОК")
    print("=" * 70)
    print()
    
    if all_passed:
        print("✅ УСПІХ! Обидва матчі виправлені правильно!")
        print()
        print("Результати:")
        print(f"  Elche ТМ 2.5: {result1} (очікувалося WON) ✅")
        print(f"  Espanyol ТМ 2.5: {result2} (очікувалося WON) ✅")
        print()
        print("Баг виправлено: ITM тепер порівнюється з голами конкретної команди,")
        print("а не з загальною сумою матчу.")
        return 0
    else:
        print("❌ ПОМИЛКА! Є проблеми з виправленням!")
        print()
        print(f"  Elche ТМ 2.5: {result1} (очікувалося WON)")
        print(f"  Espanyol ТМ 2.5: {result2} (очікувалося WON)")
        return 1

if __name__ == "__main__":
    sys.exit(main())