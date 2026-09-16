#!/usr/bin/env python3
"""
ТЕСТ: Перевірка розрізнення між ITM (індивідуальний тотал) та TM (загальний тотал)
"""
import sys
sys.path.insert(0, r'C:\Users\jvjor\.cline\data\workspaces\chat\python')
from analytics import *

analytics = BettingAnalytics()

print("=" * 70)
print("ТЕСТ: Розрізнення ITM (індивідуальний тотал) та TM (загальний тотал)")
print("=" * 70)
print()

# Сценарій: слабка домашня команда
weak_home = TeamStats('Слабка Домашня', 0.8, 2.0, 0.0, [0.5, 1.0, 0.5, 0.0, 1.0])
strong_away = TeamStats('Сильна Гостра', 2.0, 0.8, 0.0, [2.0, 1.5, 2.5, 1.0, 2.0])
ctx = MatchContext(weak_home, strong_away, 2.3, True)

preds = analytics.determine_predictions(ctx)

# Знаходимо прогнози ITM та TM
itm_pred = next((p for p in preds if p.market_type == MarketType.ITM), None)
tm_pred = next((p for p in preds if p.market_type == MarketType.TM), None)

print('1. Перевірка значень:')
print(f'   ITM (індивідуальний тотал домашньої): {itm_pred.expected_value if itm_pred else "Немає"} голів')
print(f'   TM (загальний тотал матчу): {tm_pred.expected_value if tm_pred else "Немає"} голів')
print()

if itm_pred and tm_pred:
    if itm_pred.expected_value != tm_pred.expected_value:
        print('✅ УСПІХ! ITM і TM мають РІЗНІ значення (це правильно!)')
        print(f'   ITM: {itm_pred.expected_value} (тільки одна команда)')
        print(f'   TM: {tm_pred.expected_value} (сума двох команд)')
    else:
        print('❌ ПОМИЛКА! ITM і TM мають ОДНАКОВІ значення!')
        print('   Система плутає індивідуальний тотал з загальним!')
        sys.exit(1)
else:
    print('⚠️  Не вдалося знайти обидва прогнози')
    sys.exit(1)

print()
print('2. Перевірка market_type:')
print(f'   ITM.value = "{MarketType.ITM.value}"')
print(f'   TM.value = "{MarketType.TM.value}"')
print(f'   Вони різні: {MarketType.ITM.value != MarketType.TM.value}')
print()

if MarketType.ITM.value != MarketType.TM.value:
    print('✅ УСПІХ! Розрізнення між ITM та TM працює коректно')
else:
    print('❌ ПОМИЛКА! ITM і TM мають одну мітку!')
    sys.exit(1)

print()
print('3. Перевірка найкращого ринку:')
best = analytics._select_best_market(preds)
print(f'   Обрано: {best.market_type.value}')
print(f'   Це індивідуальний тотал: {best.market_type in [MarketType.ITB, MarketType.ITM, MarketType.ITB2, MarketType.ITM2]}')
print(f'   Це загальний тотал: {best.market_type in [MarketType.TB, MarketType.TM]}')
print()

if best.market_type in [MarketType.ITB, MarketType.ITM, MarketType.ITB2, MarketType.ITM2]:
    print('✅ УСПІХ! Обрано індивідуальний тотал команди, а не загальний тотал матчу!')
    print()
    print('=' * 70)
    print('ФІНАЛЬНИЙ ВИСНОВОК')
    print('=' * 70)
    print()
    print('✅ УСПІХ! Система правильно розрізняє:')
    print('   - ITM (Індивідуальний Тотал Команди - Недотяг)')
    print('   - TM (Загальний Тотал Матчу - Недотяг)')
    print()
    print('   Помилка, коли ITM показувалося як TM, ВИПАВЕДЕНО!')
    print('   Ставки на індивідуальні тоталі тепер коректно ідентифікуються.')
    sys.exit(0)
elif best.market_type in [MarketType.TB, MarketType.TM]:
    print('❌ ПОМИЛКА! Обрано загальний тотал матчу замість індивідуального!')
    sys.exit(1)
else:
    print(f'⚠️  Непередбачуваний ринок: {best.market_type.value}')
    sys.exit(1)