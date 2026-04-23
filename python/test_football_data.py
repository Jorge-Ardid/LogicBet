#!/usr/bin/env python3
"""
Тестовий скрипт для перевірки роботи Football-Data.org API
"""

from football_data_client import FootballDataClient
from config_manager import ConfigManager

def test_football_data_api():
    print("🧪 ТЕСТУВАННЯ FOOTBALL-DATA.ORG API")
    print("=" * 50)
    
    # Ініціалізуємо клієнт з реальним ключем
    client = FootballDataClient()
    
    print(f"API ключ: {client.api_key[:8]}...")
    print(f"URL: {client.base_url}")
    
    # Тест 1: Отримання змагань
    print("\n1️⃣ Тест отримання змагань...")
    try:
        competitions = client.fetch_competitions()
        if competitions and 'competitions' in competitions:
            print(f"✅ Успішно! Отримано {len(competitions['competitions'])} змагань")
            for comp in competitions['competitions'][:3]:  # Показати перші 3
                print(f"   - {comp.get('name', 'Unknown')} ({comp.get('code', 'N/A')})")
        else:
            print("❌ Не вдалося отримати змагання")
    except Exception as e:
        print(f"❌ Помилка: {e}")
    
    # Тест 2: Отримання матчів Прем'єр-ліги
    print("\n2️⃣ Тест отримання матчів Прем'єр-ліги...")
    try:
        matches = client.fetch_matches('PL')
        if matches and 'matches' in matches:
            print(f"✅ Успішно! Отримано {len(matches['matches'])} матчів")
            for match in matches['matches'][:3]:  # Показати перші 3
                home = match.get('homeTeam', {}).get('name', 'Unknown')
                away = match.get('awayTeam', {}).get('name', 'Unknown')
                date = match.get('utcDate', 'Unknown')[:10]
                print(f"   - {date}: {home} vs {away}")
        else:
            print("❌ Не вдалося отримати матчі")
    except Exception as e:
        print(f"❌ Помилка: {e}")
    
    # Тест 3: Отримання таблиці Прем'єр-ліги
    print("\n3️⃣ Тест отримання таблиці Прем'єр-ліги...")
    try:
        standings = client.fetch_standings('PL')
        if standings and 'standings' in standings:
            table = standings['standings'][0]['table']
            print(f"✅ Успішно! Отримано таблицю з {len(table)} команд")
            for team in table[:5]:  # Показати топ-5
                name = team.get('team', {}).get('name', 'Unknown')
                points = team.get('points', 0)
                position = team.get('position', 0)
                print(f"   {position}. {name} - {points} очок")
        else:
            print("❌ Не вдалося отримати таблицю")
    except Exception as e:
        print(f"❌ Помилка: {e}")
    
    # Перевірка лімітів
    print(f"\n📊 Статус API:")
    print(f"   Залишилось запитів: {client.get_limit_left()}")
    
    print("\n" + "=" * 50)
    print("🎉 ТЕСТУВАННЯ ЗАВЕРШЕНО")

def update_config_with_key():
    """Оновлює конфігурацію з реальним API ключем"""
    print("\n🔧 ОНОВЛЕННЯ КОНФІГУРАЦІЇ")
    print("=" * 35)
    
    config = ConfigManager()
    
    # Встановлюємо реальний API ключ
    config.set_api_key('football_data_org', '72cd4a1c41ff402eba0da37f4bbc5ff6')
    
    # Налаштовуємо football-data.org як основне джерело
    config.set_data_sources(primary='football_data_org', fallback='api_football')
    
    # Зберігаємо в базу даних
    config.store_to_db()
    
    print("✅ API ключ football-data.org налаштовано")
    print("✅ Основне джерело даних: football-data.org")
    print("✅ Запасне джерело даних: api_football")
    
    config.print_status()

if __name__ == "__main__":
    # Спочатку оновлюємо конфігурацію
    update_config_with_key()
    
    # Потім тестуємо API
    test_football_data_api()
