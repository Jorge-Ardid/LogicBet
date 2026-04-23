#!/usr/bin/env python3
"""
Перевірка статусу RapidAPI та альтернативні варіанти
"""

import requests
from config_manager import ConfigManager

class RapidAPIStatusChecker:
    def __init__(self):
        self.config = ConfigManager()
        
    def check_rapidapi_account_status(self, api_key):
        """Перевіряє статус акаунту RapidAPI"""
        print("🔍 ПЕРЕВІРКА СТАТУСУ RAPIDAPI АКАУНТУ")
        print("=" * 50)
        
        # Базовий URL для перевірки статусу
        test_url = "https://rapidapi.com/apiconnect/widget/v1"
        
        headers = {
            "X-RapidAPI-Key": api_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(test_url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Акаунт активний")
                
                # Показуємо інформацію про підписки
                if 'subscriptions' in data:
                    print("📋 Активні підписки:")
                    for sub in data.get('subscriptions', []):
                        api_name = sub.get('api', {}).get('name', 'Unknown')
                        plan = sub.get('plan', {}).get('name', 'Unknown')
                        requests_left = sub.get('requests_left', 'N/A')
                        print(f"  - {api_name} ({plan}): {requests_left} запитів залишилось")
                
                return True
            else:
                print(f"❌ Помилка перевірки статусу: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Помилка запиту: {e}")
            return False
    
    def test_network_as_code_alternative(self, api_key):
        """Альтернативний тест Network-as-Code з різними URL"""
        print("\n🔄 АЛЬТЕРНАТИВНИЙ ТЕСТ NETWORK-AS-CODE")
        print("-" * 45)
        
        # Різні можливі URL
        possible_urls = [
            "https://network-as-code.p.rapidapi.com/device-status/device-reachability-status-subscriptions/v0.7",
            "https://network-as-code.p.rapidapi.com/v1/device-status",
            "https://network-as-code.p.rapidapi.com/device-reachability/v0.7"
        ]
        
        headers = {
            "x-rapidapi-host": "network-as-code.p.rapidapi.com",
            "x-rapidapi-key": api_key,
            "Content-Type": "application/json"
        }
        
        for i, url in enumerate(possible_urls, 1):
            print(f"\n📍 Тест {i}: {url}")
            
            try:
                # Спробуємо простий GET запит
                response = requests.get(url, headers=headers, timeout=10)
                
                print(f"   Статус: {response.status_code}")
                
                if response.status_code == 200:
                    print("   ✅ Успішне з'єднання!")
                    return url
                elif response.status_code == 403:
                    print("   ❌ Доступ заборонено (перевірте підписку)")
                elif response.status_code == 404:
                    print("   ❌ URL не знайдено")
                else:
                    print(f"   ❌ Помилка: {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ Виняток: {e}")
        
        return None
    
    def suggest_alternatives(self):
        """Пропонує альтернативні RapidAPI сервіси для футболу"""
        print("\n💡 АЛЬТЕРНАТИВНІ RAPIDAPI ФУТБОЛЬНІ СЕРВІСИ")
        print("=" * 55)
        
        alternatives = [
            {
                "name": "API-SPORTS",
                "url": "https://api-sports.io/api/v1",
                "description": "Безкоштовний план 100 запитів/день",
                "rapidapi": "https://rapidapi.com/apidojo/api/api-sports"
            },
            {
                "name": "Football API (PandaScore)",
                "url": "https://api.pandascore.co/api/v1",
                "description": "Безкоштовний план 100 запитів/день",
                "rapidapi": "https://rapidapi.com/apidojo/api/pandascore"
            },
            {
                "name": "Livescore API",
                "url": "https://livescore-api.p.rapidapi.com/v1",
                "description": "Безкоштовний план 100 запитів/день",
                "rapidapi": "https://rapidapi.com/apidojo/api/livescore"
            }
        ]
        
        for i, alt in enumerate(alternatives, 1):
            print(f"\n{i}. {alt['name']}")
            print(f"   URL: {alt['url']}")
            print(f"   Опис: {alt['description']}")
            print(f"   RapidAPI: {alt['rapidapi']}")
        
        return alternatives
    
    def generate_setup_instructions(self):
        """Генерує інструкції для налаштування"""
        print("\n📋 ІНСТРУКЦІЇ ДЛЯ НАЛАШТУВАННЯ")
        print("=" * 45)
        
        print("\n1. Перевірте ваш RapidAPI акаунт:")
        print("   - Зайдіть на https://rapidapi.com/")
        print("   - Перевірте активні підписки")
        print("   - Переконайтеся, що Network-as-Code активний")
        
        print("\n2. Якщо Network-as-Code неактивний:")
        print("   - Використайте альтернативні футбольні API")
        print("   - Або налаштуйте API-Football як основне джерело")
        
        print("\n3. Для додавання нового API:")
        print("   - Оновіть config_manager.py")
        print("   - Додайте новий клієнт в rapidapi_client.py")
        print("   - Інтегруйте в multi_source_sync.py")

def main():
    """Головна функція"""
    import sys
    
    checker = RapidAPIStatusChecker()
    
    # Отримуємо Network-as-Code ключ
    network_key = checker.config.get_api_key("network_as_code")
    
    if network_key and network_key != "PLACEHOLDER_KEY":
        print(f"🔑 Знайдено Network-as-Code ключ: {network_key[:8]}...")
        
        # Перевіряємо статус акаунту
        account_ok = checker.check_rapidapi_account_status(network_key)
        
        if not account_ok:
            print("\n⚠️ Проблеми з акаунтом RapidAPI")
        
        # Альтернативний тест
        working_url = checker.test_network_as_code_alternative(network_key)
        
        if working_url:
            print(f"\n✅ Робочий URL знайдено: {working_url}")
        else:
            print("\n❌ Робочий URL не знайдено")
            checker.suggest_alternatives()
    else:
        print("❌ Network-as-Code ключ не налаштовано")
    
    # Показуємо інструкції
    checker.generate_setup_instructions()

if __name__ == "__main__":
    main()
