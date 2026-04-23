#!/usr/bin/env python3
"""
Тестування RapidAPI клієнтів
"""

from rapidapi_client import NetworkAsCodeClient, create_rapidapi_client
from config_manager import ConfigManager

def test_network_as_code():
    """Тестування Network-as-Code API"""
    print("🧪 ТЕСТУВАННЯ NETWORK-AS-CODE API")
    print("=" * 50)
    
    # Ініціалізуємо клієнт з реальним ключем
    client = NetworkAsCodeClient()
    
    print(f"API ключ: {client.api_key[:8]}...")
    print(f"URL: {client.base_url}")
    
    # Тест з'єднання
    connection_ok = client.test_connection()
    
    if connection_ok:
        print("✅ З'єднання успішне!")
        
        # Тест створення підписки
        print("\n🔄 Тест створення підписки...")
        try:
            subscription = client.create_device_subscription(
                phone_number="199999991000",
                sink_url="https://webhook.example.com/device-status",
                max_events=3
            )
            
            if subscription:
                print("✅ Підписку створено успішно!")
                print(f"ID підписки: {subscription.get('id', 'N/A')}")
            else:
                print("❌ Не вдалося створити підписку")
                
        except Exception as e:
            print(f"❌ Помилка створення підписки: {e}")
    else:
        print("❌ З'єднання не вдалося")
    
    # Показуємо статус
    status = client.get_status()
    print(f"\n📊 Статус клієнта:")
    for key, value in status.items():
        print(f"  {key}: {value}")

def test_generic_rapidapi():
    """Тестування універсального RapidAPI клієнта"""
    print("\n🧪 ТЕСТУВАННЯ УНІВЕРСАЛЬНОГО RAPIDAPI")
    print("=" * 50)
    
    try:
        client = create_rapidapi_client("generic_football")
        print("✅ Універсальний клієнт створено")
        
        status = client.get_status()
        print(f"📊 Статус: {status}")
        
    except Exception as e:
        print(f"❌ Помилка: {e}")

def test_all_rapidapi_services():
    """Тестування всіх налаштованих RapidAPI сервісів"""
    print("\n🧪 ТЕСТУВАННЯ ВСІХ RAPIDAPI СЕРВІСІВ")
    print("=" * 55)
    
    config = ConfigManager()
    config.load_from_db()
    
    services = [
        ("network_as_code", "Network-as-Code"),
        ("rapidapi_generic", "Generic Football API")
    ]
    
    for service_key, service_name in services:
        print(f"\n🔍 Перевірка {service_name}...")
        
        if config.is_api_key_valid(service_key):
            api_key = config.get_api_key(service_key)
            print(f"  ✅ API ключ налаштовано: {api_key[:8]}...")
            
            try:
                if service_key == "network_as_code":
                    client = NetworkAsCodeClient(api_key=api_key)
                else:
                    client = create_rapidapi_client("generic_football", api_key=api_key)
                
                connection_ok = client.test_connection()
                if connection_ok:
                    print(f"  ✅ {service_name}: З'єднання успішне")
                else:
                    print(f"  ❌ {service_name}: З'єднання не вдалося")
                    
            except Exception as e:
                print(f"  ❌ {service_name}: Помилка - {e}")
        else:
            print(f"  ❌ {service_name}: API ключ не налаштовано")

def main():
    """Головна функція"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "network":
            test_network_as_code()
        elif command == "generic":
            test_generic_rapidapi()
        elif command == "all":
            test_all_rapidapi_services()
        else:
            print("Доступні команди:")
            print("  network - тестувати Network-as-Code API")
            print("  generic - тестувати універсальний RapidAPI")
            print("  all     - тестувати всі сервіси")
    else:
        # За замовчуванням тестуємо всі
        test_all_rapidapi_services()

if __name__ == "__main__":
    main()
