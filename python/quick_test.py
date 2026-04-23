#!/usr/bin/env python3
"""
Швидкий тест системи після виправлень
"""

from multi_source_sync import MultiSourceSyncEngine
from config_manager import ConfigManager

def quick_test():
    print("🧪 ШВИДКИЙ ТЕСТ СИСТЕМИ")
    print("=" * 40)
    
    # Тест конфігурації
    config = ConfigManager()
    config.load_from_db()
    
    print("\n📋 СТАТУС КОНФІГУРАЦІЇ:")
    print(f"  Football-Data.org ключ: {'✅' if config.is_api_key_valid('football_data_org') else '❌'}")
    print(f"  API-Football ключ: {'✅' if config.is_api_key_valid('api_football') else '❌'}")
    print(f"  Основне джерело: {config.get_primary_source()}")
    print(f"  Запасне джерело: {config.get_fallback_source()}")
    
    # Тест движка
    print("\n🔧 СТАТУС ДВИЖКА:")
    engine = MultiSourceSyncEngine()
    
    print(f"  Football-Data.org клієнт: {'✅ Активний' if engine.football_data_org else '❌ Неактивний'}")
    print(f"  API-Football клієнт: {'✅ Активний' if engine.api_football else '❌ Неактивний'}")
    
    if engine.football_data_org:
        print(f"  Залишилось запитів (Football-Data.org): {engine.football_data_org.get_limit_left()}")
    
    # Тест одного запиту
    if engine.football_data_org:
        print("\n🔄 ТЕСТОВИЙ ЗАПИТ ДО API...")
        try:
            competitions = engine.football_data_org.fetch_competitions()
            if competitions and 'competitions' in competitions:
                print(f"  ✅ Успішно! Отримано {len(competitions['competitions'])} змагань")
                # Показати перші 3
                for comp in competitions['competitions'][:3]:
                    print(f"     - {comp.get('name', 'Unknown')}")
            else:
                print("  ❌ Не вдалося отримати змагання")
        except Exception as e:
            print(f"  ❌ Помилка: {e}")
    
    print("\n" + "=" * 40)
    print("🎉 ТЕСТ ЗАВЕРШЕНО")
    
    # Рекомендації
    print("\n💡 РЕКОМЕНДАЦІЇ:")
    if not engine.football_data_org:
        print("  - Налаштуйте API ключ Football-Data.org")
    if not engine.api_football:
        print("  - Розгляньте налаштування API-Football як запасне джерело")
    
    print("  - Використовуйте python main.py --force для примусової синхронізації")
    print("  - Використовуйте python main.py для звичайної синхронізації")

if __name__ == "__main__":
    quick_test()
