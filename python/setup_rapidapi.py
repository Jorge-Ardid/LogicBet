#!/usr/bin/env python3
"""
Налаштування RapidAPI ключів
"""

from config_manager import ConfigManager

def setup_rapidapi_keys():
    """Налаштування RapidAPI ключів"""
    print("🔧 НАЛАШТУВАННЯ RAPIDAPI КЛЮЧІВ")
    print("=" * 45)
    
    config = ConfigManager()
    
    # Network-as-Code ключ (вже є)
    network_key = "3725c32b04mshb942c2df0e3ab79p18f60djsn14472b9a742"
    config.set_api_key("network_as_code", network_key)
    print(f"✅ Network-as-Code ключ налаштовано")
    
    # Generic RapidAPI ключ (поки placeholder)
    generic_key = "PLACEHOLDER_KEY"
    config.set_api_key("rapidapi_generic", generic_key)
    print("⚠️ Generic RapidAPI ключ: placeholder (потрібен реальний ключ)")
    
    # Зберігаємо в базу даних
    config.store_to_db()
    print("✅ Ключі збережено в базу даних")
    
    # Показуємо статус
    print("\n📊 СТАТУС ПІСЛЯ НАЛАШТУВАННЯ:")
    for service in ["network_as_code", "rapidapi_generic"]:
        key = config.get_api_key(service)
        is_valid = config.is_api_key_valid(service)
        status = "✅ Активний" if is_valid else "❌ Неактивний"
        masked = key[:8] + "..." if key != "PLACEHOLDER_KEY" else "PLACEHOLDER"
        print(f"  {service}: {status} ({masked})")

if __name__ == "__main__":
    setup_rapidapi_keys()
