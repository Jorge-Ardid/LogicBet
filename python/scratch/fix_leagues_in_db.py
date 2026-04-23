from database import LogicBetDB

db = LogicBetDB()
conn = db.get_connection()
cursor = conn.cursor()

# Mapping of ID to correct Ukrainian Name
mapping = {
    39: "Прем'єр-ліга (Англія)",
    140: "Ла Ліга (Іспанія)",
    78: "Бундесліга (Німеччина)",
    61: "Ліга 1 (Франція)",
    135: "Серія А (Італія)",
    2: "Ліга Чемпіонів",
    3: "Ліга Європи",
    848: "Ліга Конференцій",
    88: "Ередивізі (Нідерланди)",
    94: "Прімейра-ліга (Португалія)",
    40: "Чемпіоншип (Англія)"
}

print("=== ВИПРАВЛЕННЯ НАЗВ ЛІГ У БАЗІ ДАНИХ ===")
updated_total = 0

for l_id, correct_name in mapping.items():
    cursor.execute("UPDATE matches SET league = ? WHERE league_id = ?", (correct_name, l_id))
    updated_total += cursor.rowcount
    if cursor.rowcount > 0:
        print(f"  - Виправлено: {correct_name} (ID {l_id}) -> {cursor.rowcount} матчів")

conn.commit()
conn.close()

print(f"\nГотово! Всього виправлено записів: {updated_total}")
