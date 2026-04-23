#!/usr/bin/env python3
"""
Розумна синхронізація з урахуванням лімітів API
Автоматично перевіряє ліміти і поновлює дані коли це можливо
"""

import time
from datetime import datetime, timedelta
from multi_source_sync import MultiSourceSyncEngine
from config_manager import ConfigManager

class SmartSyncManager:
    def __init__(self):
        self.engine = MultiSourceSyncEngine()
        self.config = ConfigManager()
        
    def check_and_sync(self):
        """Перевіряє ліміти і синхронізує якщо можливо"""
        print("🤖 РОЗУНА СИНХРОНІЗАЦІЯ")
        print("=" * 50)
        
        # Перевіряємо стан API
        if self.engine.football_data_org:
            available_requests = self.engine.football_data_org.get_limit_left()
            print(f"📊 Доступно запитів: {available_requests}")
            
            if available_requests >= 8:
                print("✅ Багато запитів доступно - повна синхронізація")
                return self.run_smart_sync(full_sync=True)
            elif available_requests >= 3:
                print("⚠️ Обмежена кількість запитів - часткова синхронізація")
                return self.run_smart_sync(full_sync=False)
            else:
                print("❌ Замало запитів - перевіряємо час скидання")
                return self.check_limit_reset()
        else:
            print("❌ API клієнт не активний")
            return False
    
    def check_limit_reset(self):
        """Перевіряє чи скинулися ліміти"""
        print("\n🔄 ПЕРЕВІРКА СКИДАННЯ ЛІМІТІВ")
        
        last_check = float(self.engine.db.get_config("last_limit_check") or 0)
        current_time = time.time()
        
        # Якщо пройшло більше 1 години - пробуємо знову
        if current_time - last_check > 3600:
            print("🧪 Тестуємо API...")
            
            # Робимо тестовий запит
            test_result = self.engine.football_data_org.fetch_competitions()
            
            if test_result:
                new_requests = self.engine.football_data_org.get_limit_left()
                print(f"✅ Ліміти скинутись! Доступно: {new_requests}")
                self.engine.db.set_config("last_limit_check", current_time)
                
                if new_requests >= 3:
                    return self.run_smart_sync(full_sync=False)
                else:
                    print("⏰ Ліміти ще низькі, чекаємо...")
                    return self.schedule_next_check()
            else:
                print("❌ Ліміти ще не скинутись")
                self.engine.db.set_config("last_limit_check", current_time)
                return self.schedule_next_check()
        else:
            minutes_until_check = int((3600 - (current_time - last_check)) / 60)
            print(f"⏰ Наступна перевірка через {minutes_until_check} хвилин")
            return False
    
    def run_smart_sync(self, full_sync=True):
        """Виконує розумну синхронізацію"""
        if full_sync:
            print("\n🔄 ПОВНА СИНХРОНІЗАЦІЯ")
            return self.engine.run_full_sync(force_sync=True)
        else:
            print("\n🔄 ЧАСТКОВА СИНХРОНІЗАЦІЯ")
            return self.engine.sync_live_data()
    
    def schedule_next_check(self):
        """Планує наступну перевірку"""
        last_sync = float(self.engine.db.get_config("last_sync_time") or 0)
        current_time = time.time()
        
        # Встановлюємо час наступної перевірки через 1 годину
        next_check = current_time + 3600
        self.engine.db.set_config("next_auto_check", str(next_check))
        
        next_check_time = datetime.fromtimestamp(next_check)
        print(f"📅 Наступна автоматична перевірка: {next_check_time.strftime('%H:%M')}")
        return True
    
    def auto_sync_loop(self, max_iterations=10):
        """Автоматичний цикл синхронізації"""
        print("🔄 ЗАПУСК АВТОМАТИЧНОЇ СИНХРОНІЗАЦІЇ")
        print(f"Максимум ітерацій: {max_iterations}")
        print("=" * 50)
        
        for i in range(max_iterations):
            print(f"\n📍 ІТЕРАЦІЯ {i+1}/{max_iterations}")
            print("-" * 30)
            
            success = self.check_and_sync()
            
            if success:
                print("✅ Синхронізація успішна")
                
                # Перевіряємо чи є ще запити
                if self.engine.football_data_org:
                    remaining = self.engine.football_data_org.get_limit_left()
                    if remaining >= 3:
                        print("🔄 Продовжуємо синхронізацію...")
                        time.sleep(5)  # Невелика пауза між ітераціями
                        continue
                    else:
                        print("⏹️ Запити вичерпано, завершуємо")
                        break
                else:
                    break
            else:
                print("❌ Синхронізація не вдалась")
                break
        
        print(f"\n🏁 ЗАВЕРШЕНО ПОСЛЯ {i+1} ІТЕРАЦІЙ")
    
    def get_status(self):
        """Показує поточний статус"""
        print("📊 ПОТОЧНИЙ СТАТУС")
        print("=" * 30)
        
        if self.engine.football_data_org:
            requests_left = self.engine.football_data_org.get_limit_left()
            print(f"Запитів доступно: {requests_left}")
            
            last_sync = self.engine.db.get_config("last_sync_time")
            if last_sync:
                sync_time = datetime.fromtimestamp(float(last_sync))
                print(f"Остання синхронізація: {sync_time.strftime('%Y-%m-%d %H:%M')}")
            
            next_check = self.engine.db.get_config("next_auto_check")
            if next_check:
                check_time = datetime.fromtimestamp(float(next_check))
                print(f"Наступна перевірка: {check_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            print("❌ API не налаштовано")

def main():
    """Головна функція"""
    import sys
    
    manager = SmartSyncManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "status":
            manager.get_status()
        elif command == "check":
            manager.check_and_sync()
        elif command == "auto":
            max_iter = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            manager.auto_sync_loop(max_iterations=max_iter)
        else:
            print("Доступні команди:")
            print("  status  - показати статус")
            print("  check   - перевірити і синхронізувати")
            print("  auto N  - автоматична синхронізація (N ітерацій)")
    else:
        # За замовчуванням - перевіряє і синхронізує
        manager.check_and_sync()

if __name__ == "__main__":
    main()
