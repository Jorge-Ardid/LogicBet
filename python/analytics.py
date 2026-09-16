#!/usr/bin/env python3
"""
 Betting Analytics Module

Розраховує прогнози для індивідуальних тоталів команд (ITB/ITM)
та загального тоталу матчу (TB/TM).

Пріоритет: Індивідуальні тоталі команд (ITB/ITM) мають вищий пріоритет,
оскільки дозволяють точніше оцінити очікуваний результативність кожної команди окремо.
"""

import math
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum


class MarketType(Enum):
    """Типи ринків для ставок."""
    ITB = "ITB"
    ITM = "ITM"
    ITB2 = "ITB2"
    ITM2 = "ITM2"
    TB = "TB"
    TM = "TM"


@dataclass
class TeamStats:
    """Статистика команди для аналізу."""
    name: str
    avg_goals_scored: float
    avg_goals_conceded: float
    home_advantage: float = 0.0
    form: List[float] = None
    attack_strength: float = 1.0
    defense_strength: float = 1.0
    
    def __post_init__(self):
        if self.form is None:
            self.form = []


@dataclass
class MatchContext:
    """Контекст матчу для аналізу."""
    home_team: TeamStats
    away_team: TeamStats
    league_avg_goals: float = 2.5
    is_high_stakes: bool = False
    weather_factor: float = 1.0


@dataclass
class Prediction:
    """Прогноз для конкретного ринку."""
    market_type: MarketType
    expected_value: float
    probability: float
    confidence: float
    reasoning: str


class BettingAnalytics:
    """Клас для аналізу ставок та формування прогнозів."""
    
    def __init__(self):
        self.default_threshold = 0.65
    
    def calculate_team_expected_goals(self, team: TeamStats, opponent: TeamStats,
                                       context: MatchContext, is_home: bool) -> Tuple[float, float]:
        """Розраховує очікувану результативність команди окремо."""
        base_attack = team.avg_goals_scored * team.attack_strength
        base_defense_opponent = opponent.avg_goals_conceded * opponent.defense_strength
        home_factor = 1.0 + (team.home_advantage if is_home else 0.0)
        
        form_factor = 1.0
        if team.form:
            recent_avg = sum(team.form[-5:]) / min(len(team.form), 5)
            form_factor = 0.9 + (recent_avg / 3.0)
        
        expected_scored = ((base_attack + base_defense_opponent) / 2.0 * home_factor * form_factor * context.weather_factor)
        
        base_defense = team.avg_goals_conceded * team.defense_strength
        base_attack_opponent = opponent.avg_goals_scored * opponent.attack_strength
        expected_conceded = ((base_defense + base_attack_opponent) / 2.0 * (1.0 - team.home_advantage if is_home else 1.0) * form_factor * context.weather_factor)
        
        if context.is_high_stakes:
            expected_scored *= 1.05
        
        return round(expected_scored, 2), round(expected_conceded, 2)

    def determine_predictions(self, context: MatchContext) -> List[Prediction]:
        """
        Визначає прогнози для матчу.
        ПРИОРИТЕТ: Індивідуальні тоталі команд (ITB/ITM) мають вищий пріоритет.
        """
        predictions = []
        
        home_exp, _ = self.calculate_team_expected_goals(context.home_team, context.away_team, context, True)
        away_exp, _ = self.calculate_team_expected_goals(context.away_team, context.home_team, context, False)
        
        home_line = 1.5
        home_prob_over = self._calc_prob_over(home_exp, home_line)
        home_prob_under = 1.0 - home_prob_over
        
        predictions.append(Prediction(MarketType.ITB, home_exp, home_prob_over, self._calc_conf(home_exp, home_line, home_prob_over),
            f"Домашня команда очікується на рівні {home_exp} голів. Ймовірність перевищення {home_line} - {home_prob_over:.1%}"))
        predictions.append(Prediction(MarketType.ITM, home_exp, home_prob_under, self._calc_conf(home_exp, home_line, home_prob_under),
            f"Домашня команда очікується на рівні {home_exp} голів. Ймовірність недотягу до {home_line} - {home_prob_under:.1%}"))
        
        away_line = 1.5
        away_prob_over = self._calc_prob_over(away_exp, away_line)
        away_prob_under = 1.0 - away_prob_over
        
        predictions.append(Prediction(MarketType.ITB2, away_exp, away_prob_over, self._calc_conf(away_exp, away_line, away_prob_over),
            f"Гостра команда очікується на рівні {away_exp} голів. Ймовірність перевищення {away_line} - {away_prob_over:.1%}"))
        predictions.append(Prediction(MarketType.ITM2, away_exp, away_prob_under, self._calc_conf(away_exp, away_line, away_prob_under),
            f"Гостра команда очікується на рівні {away_exp} голів. Ймовірність недотягу до {away_line} - {away_prob_under:.1%}"))
        
        match_exp = home_exp + away_exp
        match_line = 2.5
        match_prob_over = self._calc_prob_over(match_exp, match_line)
        match_prob_under = 1.0 - match_prob_over
        
        predictions.append(Prediction(MarketType.TB, match_exp, match_prob_over, self._calc_conf(match_exp, match_line, match_prob_over) * 0.9,
            f"Загальний тотал матчу очікується на рівні {match_exp} голів. Рекомендовано зосередитися на індивідуальних тоталах."))
        predictions.append(Prediction(MarketType.TM, match_exp, match_prob_under, self._calc_conf(match_exp, match_line, match_prob_under) * 0.9,
            f"Загальний тотал матчу очікується на рівні {match_exp} голів. Рекомендовано зосередитися на індивідуальних тоталах."))
        
        priority = {MarketType.ITB: 0, MarketType.ITM: 0, MarketType.ITB2: 1, MarketType.ITM2: 1, MarketType.TB: 2, MarketType.TM: 2}
        predictions.sort(key=lambda p: (priority.get(p.market_type, 3), -p.confidence))
        return predictions
    
    def _select_best_market(self, predictions: List[Prediction]) -> Optional[Prediction]:
        """Обирає найкращий ринок. Пріоритет індивідуальним тоталам (ITB/ITM)."""
        viable = [p for p in predictions if p.confidence >= self.default_threshold and p.probability > 0.4]
        if not viable:
            return None
        
        market_priority = {MarketType.ITB: 0, MarketType.ITM: 0, MarketType.ITB2: 1, MarketType.ITM2: 1, MarketType.TB: 2, MarketType.TM: 2}
        best = max(viable, key=lambda p: (-market_priority.get(p.market_type, 3), p.confidence, p.probability))
        return best
    
    def _calc_prob_over(self, expected_value: float, line: float) -> float:
        if expected_value <= 0:
            return 0.0
        std_dev = math.sqrt(expected_value) if expected_value > 0 else 1.0
        z = (expected_value - line) / std_dev
        prob = 0.5 + 0.5 * math.erf(z / math.sqrt(2))
        return max(0.05, min(0.95, prob))
    
    def _calc_conf(self, expected_value: float, line: float, probability: float) -> float:
        base_conf = abs(probability - 0.5) * 2
        deviation = abs(expected_value - line)
        dev_factor = min(1.0, deviation / 1.0)
        confidence = 0.3 + 0.5 * base_conf + 0.2 * dev_factor
        return round(min(0.95, max(0.1, confidence)), 2)
def check_market_result(
    market_type: MarketType,
    home_goals: int,
    away_goals: int,
    is_home_team: bool = True,
    line: float = 1.5
) -> Tuple[str, str]:
    """
    Перевіряє результат ставки з урахуванням реальних голів.
    
    КЛЮЧОВИЙ БАГ ФІКС: Для індивідуальних тоталів (ITB/ITM) порівнюємо
    ЗГОЛИ КОНКРЕТНОЇ КОМАНДИ, а не загальну суму матчу!
    
    Args:
        market_type: Тип ринку (ITB, ITM, ITB2, ITM2, TB, TM)
        home_goals: Голи домашньої команди
        away_goals: Голи гострої команди
        is_home_team: Чи ставка на домашню команду (для ITB/ITM)
        line: Лінія тоталу
        
    Returns:
        Tuple[str, str]: (результат "WON"/"LOST", пояснення)
    """
    # Визначаємо, чії готи перевіряти
    if market_type in [MarketType.ITB, MarketType.ITM]:
        # Ставка на домашню команду - перевіряємо тільки її готи
        team_goals = home_goals
        team_name = "Домашня"
    elif market_type in [MarketType.ITB2, MarketType.ITM2]:
        # Ставка на гостру команду - перевіряємо тільки її готи
        team_goals = away_goals
        team_name = "Гостра"
    elif market_type in [MarketType.TB, MarketType.TM]:
        # Загальний тотал - перевіряємо суму обох команд
        team_goals = home_goals + away_goals
        team_name = "Матч (загальний)"
    else:
        return "LOST", "Невідомий тип ринку"
    
    # Розраховуємо результат
    if market_type in [MarketType.ITB, MarketType.ITB2, MarketType.TB]:
        # Over (Перевищення) - ставка виграє, якщо більше ніж лінія
        if team_goals > line:
            result = "WON"
            explanation = f"{team_name} забили {team_goals} гол(а/ів), більше ніж лінія {line} → ВИГРАШ"
        else:
            result = "LOST"
            explanation = f"{team_name} забили {team_goals} гол(а/ів), менше або дорівнює лінії {line} → ПРОГРАШ"
    else:  # MarketType.ITM, MarketType.ITM2, MarketType.TM
        # Under (Недотяг) - ставка виграє, якщо менше ніж лінія
        if team_goals < line:
            result = "WON"
            explanation = f"{team_name} забили {team_goals} гол(а/ів), менше ніж лінія {line} → ВИГРАШ"
        else:
            result = "LOST"
            explanation = f"{team_name} забили {team_goals} гол(а/ів), більше або дорівнює лінії {line} → ПРОГРАШ"
    
    return result, explanation


def test_elche_real_madrid():
    """Тест баг-сценарію: Elche — Real Madrid (2:3)"""
    print("=" * 70)
    print("ТЕСТ: Elche — Real Madrid (2:3)")
    print("Ставка: Elche ТМ 2.5 (Індивідуальний Тотал - Недотяг)")
    print("=" * 70)
    print()
    
    home_goals = 2  # Elche забили 2
    away_goals = 3  # Real Madrid забили 3
    line = 2.5
    
    print(f"Результат матчу: Elche {home_goals} - {away_goals} Real Madrid")
    print(f"Загальна сума: {home_goals + away_goals}")
    print()
    
    # ПОМИЛКА (як було раніше)
    print("❌ Раніше (помилково):")
    total = home_goals + away_goals  # 5
    if total > line:
        print(f"  Ставка = LOST (помилково!)")
        print(f"  Чому? Порівнювали з загальною сумою: {total} > {line}")
    print()
    
    # КОРЕКТНО (як має бути)
    print("✅ Тепер (правильно):")
    result, explanation = check_market_result(
        MarketType.ITM,  # Или MarketType.ITM для домашньої команди
        home_goals=home_goals,
        away_goals=away_goals,
        is_home_team=True,  # Elche - домашня
        line=line
    )
    print(f"  Результат: {result}")
    print(f"  Пояснення: {explanation}")
    print()
    
    if result == "WON":
        print("✅ УСПІХ! Elche ТМ 2.5 = WON (правильно!)")
        return True
    return False


def run_tests():
    print("=" * 70)
    print("ТЕСТУВАННЯ АНАЛІТИЧНОГО МОДУЛЯ")
    print("=" * 70)
    print()
    
    analytics = BettingAnalytics()
    
    print("СЦЕНАРІЙ 1: Сильна домашня команда vs слабка гостра")
    print("-" * 70)
    
    strong_home = TeamStats("Сильна Домашня", 2.0, 0.8, 0.3, [2.0, 1.5, 2.5, 1.0, 2.0], 1.2, 0.9)
    weak_away = TeamStats("Слабка Гостра", 0.8, 2.0, 0.0, [0.5, 1.0, 0.5, 0.0, 1.0], 0.8, 1.2)
    context1 = MatchContext(strong_home, weak_away, 2.3, True)
    preds1 = analytics.determine_predictions(context1)
    
    print(f"\nОчікувана результативність:")
    print(f"  Домашня: ~{preds1[0].expected_value} голів (індивідуальний тотал)")
    print(f"  Гостра: ~{preds1[2].expected_value} голів (індивідуальний тотал)")
    print(f"  Загальний тотал: ~{preds1[4].expected_value} голів")
    
    print(f"\nПРІОРИТЕТНІ ПРОГНОЗИ (індивідуальні тоталі команд):")
    for p in preds1[:4]:
        print(f"  {p.market_type.value}: очікується={p.expected_value}, ймовірність={p.probability:.1%}, впевненість={p.confidence:.1%}")
        print(f"    → {p.reasoning}")
    
    print(f"\nРЕЗЕРВНІ ПРОГНОЗИ (загальний тотал матчу):")
    for p in preds1[4:]:
        print(f"  {p.market_type.value}: очікується={p.expected_value}, ймовірність={p.probability:.1%}, впевненість={p.confidence:.1%}")
    
    best1 = analytics._select_best_market(preds1)
    print(f"\n🏆 НАЙКРАЩИЙ РИНОК ДЛЯ СТАВКИ: {best1.market_type.value}")
    print(f"   Очікуване: {best1.expected_value}, Ймовірність: {best1.probability:.1%}, Впевненість: {best1.confidence:.1%}")
    
    print("\n" + "=" * 70)
    print("СЦЕНАРІЙ 2: Збалансований матч")
    print("-" * 70)
    
    balanced_home = TeamStats("Збалансована Домашня", 1.5, 1.2, 0.2, [1.5, 1.0, 2.0, 1.0, 1.5])
    balanced_away = TeamStats("Збалансована Гостра", 1.3, 1.4, 0.0, [1.0, 1.5, 1.0, 0.5, 1.5])
    context2 = MatchContext(balanced_home, balanced_away, 2.5, False)
    preds2 = analytics.determine_predictions(context2)
    
    print(f"\nОчікувана результативність:")
    print(f"  Домашня: ~{preds2[0].expected_value} голів")
    print(f"  Гостра: ~{preds2[2].expected_value} голів")
    print(f"  Загальний тотал: ~{preds2[4].expected_value} голів")
    
    print(f"\nПРІОРИТЕТНІ ПРОГНОЗИ (індивідуальні тоталі команд):")
    for p in preds2[:4]:
        print(f"  {p.market_type.value}: очікується={p.expected_value}, ймовірність={p.probability:.1%}, впевненість={p.confidence:.1%}")
    
    print(f"\nРЕЗЕРВНІ ПРОГНОЗИ (загальний тотал матчу):")
    for p in preds2[4:]:
        print(f"  {p.market_type.value}: очікується={p.expected_value}, ймовірність={p.probability:.1%}, впевненість={p.confidence:.1%}")
    
    best2 = analytics._select_best_market(preds2)
    print(f"\n🏆 НАЙКРАЩИЙ РИНОК ДЛЯ СТАВКИ: {best2.market_type.value}")
    print(f"   Очікуване: {best2.expected_value}, Ймовірність: {best2.probability:.1%}, Впевненість: {best2.confidence:.1%}")
    
    print("\n" + "=" * 70)
    print("ВЕРИФИКАЦИЯ: Пріоритет індивідуальним тоталам")
    print("-" * 70)
    
    ind1 = best1.market_type in [MarketType.ITB, MarketType.ITM, MarketType.ITB2, MarketType.ITM2]
    ind2 = best2.market_type in [MarketType.ITB, MarketType.ITM, MarketType.ITB2, MarketType.ITM2]
    
    print(f"Сценарій 1: {best1.market_type.value} - {'✓ Індивідуальний тотал' if ind1 else '✗ ПОМИЛКА!'}")
    print(f"Сценарій 2: {best2.market_type.value} - {'✓ Індивідуальний тотал' if ind2 else '✗ ПОМИЛКА!'}")
    
    if ind1 and ind2:
        print("\n✅ Успішно! Пріоритет індивідуальним тоталам команд (ITB/ITM) відновлено.")
        return True
    else:
        print("\n❌ ПОМИЛКА! Використовується загальний тотал матчу.")
        return False

def test_bug_fix():
    """Тест виправлення багу: ITM має порівнюватися з голами команди, а не з матчем"""
    print()
    print("=" * 70)
    print("ТЕСТ ВИПАВЛЕННЯ БАГУ: Розрахунок ITM/ITB")
    print("=" * 70)
    print()
    
    all_passed = True
    
    # Тест 1: Elche — Real Madrid (2:3)
    print("МАТЧ 1: Elche — Real Madrid (2:3)")
    print("-" * 70)
    home1, away1 = 2, 3
    line = 2.5
    
    print(f"Результат: Elche {home1} - {away1} Real Madrid")
    print(f"Ставка: Elche ТМ {line} (Індивідуальний тотал - Недотяг)")
    print()
    
    # Перевірка правильного розрахунку
    result1, expl1 = check_market_result(
        MarketType.ITM,
        home_goals=home1,
        away_goals=away1,
        is_home_team=True,  # Elche - домашня
        line=line
    )
    
    print(f"Результат: {result1}")
    print(f"Пояснення: {expl1}")
    print()
    
    if result1 == "WON":
        print("✅ УСПІХ! Elche ТМ 2.5 = WON (правильно, бо 2 < 2.5)")
    else:
        print("❌ ПОМИЛКА! Має бути WON!")
        all_passed = False
    
    print()
    
    # Тест 2: Espanyol — Деяка команда (1:3) - припустимо
    print("МАТЧ 2: Espanyol — Суперник (1:3)")
    print("-" * 70)
    home2, away2 = 1, 3
    
    print(f"Результат: Espanyol {home2} - {away2} Суперник")
    print(f"Ставка: Espanyol ТМ {line} (Індивідуальний тотал - Недотяг)")
    print()
    
    result2, expl2 = check_market_result(
        MarketType.ITM,
        home_goals=home2,
        away_goals=away2,
        is_home_team=True,  # Espanyol - домашня
        line=line
    )
    
    print(f"Результат: {result2}")
    print(f"Пояснення: {expl2}")
    print()
    
    if result2 == "WON":
        print("✅ УСПІХ! Espanyol ТМ 2.5 = WON (правильно, бо 1 < 2.5)")
    else:
        print("❌ ПОМИЛКА! Має бути WON!")
        all_passed = False
    
    print()
    
    # Додатковий тест: Перевірка, що TM (загальний тотал) все ще працює правильно
    print("ДОДАТКОВО: Перевірка TM (Загальний тотал матчу)")
    print("-" * 70)
    print(f"Загальна сума: {home1 + away1} голів")
    print(f"TM {line} (Загальний тотал - Недотяг)")
    print()
    
    result3, expl3 = check_market_result(
        MarketType.TM,
        home_goals=home1,
        away_goals=away1,
        is_home_team=True,
        line=line
    )
    
    print(f"Результат: {result3}")
    print(f"Пояснення: {expl3}")
    print()
    
    if result3 == "LOST":
        print("✅ УСПІХ! TM 2.5 = LOST (правильно, бо 5 > 2.5)")
    else:
        print("❌ ПОМИЛКА! Має бути LOST!")
        all_passed = False
    
    print()
    
    if all_passed:
        print("=" * 70)
        print("✅ УСПІХ! Всі тести пройдено!")
        print("=" * 70)
        print()
        print("ВИПАВЛЕНО:")
        print("  ❌ Баг: ITM порівнювалося з загальною сумою матчу")
        print("  ✅ Фікс: ITM порівнюється з голами конкретної команди")
        print()
        print("Приклад:")
        print("  Elche — Real Madrid (2:3)")
        print("  Elche ТМ 2.5:")
        print("    ❌ Було: LOST (5 > 2.5 - загальна сума)")
        print("    ✅ Стало: WON (2 < 2.5 - тільки Elche)")
        return True
    else:
        return False


if __name__ == "__main__":
    # Спочатку запускаємо основні тести
    success = run_tests()
    
    # Потім тест виправлення багу
    print()
    print("=" * 70)
    print("ДОДАТКОВИЙ ТЕСТ: Виправлення багу з ITM/ITB")
    print("=" * 70)
    print()
    
    bug_fix_success = test_bug_fix()
    
    # Завершення
    if success and bug_fix_success:
        sys.exit(0)
    else:
        sys.exit(1)
