"""Скидає таймер кулдауну щоб наступний запуск main.py зробив повний синк з API."""
from database import LogicBetDB

db = LogicBetDB()
db.set_config("last_sync_time", "0")
print("✅ Кулдаун скинуто. Запустіть main.py — він зробить повний синк з API.")
