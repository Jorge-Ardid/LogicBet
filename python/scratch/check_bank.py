from database import LogicBetDB

db = LogicBetDB()
conn = db.get_connection()
cursor = conn.cursor()

print("=== ПЕРЕВІРКА БАНКУ ===")
cursor.execute("SELECT key, value FROM config WHERE key IN ('bankroll', 'balance', 'starting_bankroll')")
configs = cursor.fetchall()
for k, v in configs:
    print(f"{k}: {v}")

print("\n=== ВАШІ ОСТАННІ СТАВКИ ===")
cursor.execute("""
    SELECT ub.id, m.date, t1.name, t2.name, ub.selection, ub.stake, ub.odd, ub.status, m.home_score, m.away_score
    FROM user_bets ub
    JOIN matches m ON ub.match_id = m.id
    JOIN teams t1 ON m.home_team_id = t1.id
    JOIN teams t2 ON m.away_team_id = t2.id
    ORDER BY m.date DESC LIMIT 10
""")
bets = cursor.fetchall()
if not bets:
    print("Ставок не знайдено.")
for b in bets:
    print(f"ID: {b[0]} | {b[2]} vs {b[3]} | Ставка: {b[4]} | Сума: {b[5]} | Коеф: {b[6]} | Статус: {b[7]} | Рахунок: {b[8]}:{b[9]}")

conn.close()
