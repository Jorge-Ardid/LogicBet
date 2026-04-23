import sqlite3
import numpy as np
db_path='c:/Users/jvjor/OneDrive/Рабочий стол/Yuri/Footboll/godot_app/logicbet.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM teams')
print(f'Teams: {c.fetchone()[0]}')
c.execute('SELECT COUNT(*) FROM matches')
print(f'Matches: {c.fetchone()[0]}')
c.execute('SELECT COUNT(*) FROM predictions')
print(f'Predictions: {c.fetchone()[0]}')
c.execute('SELECT COUNT(*) FROM predictions WHERE is_hit IS NOT NULL')
num_eval=c.fetchone()[0]
print(f'Evaluated: {num_eval}')
c.execute('SELECT COUNT(*) FROM predictions WHERE is_hit = 1')
num_won=c.fetchone()[0]
print(f'Won: {num_won}')
print(f'Accuracy: {num_won/num_eval*100 if num_eval > 0 else 0:.2f}%')
c.execute('SELECT COUNT(*) as cnt FROM matches GROUP BY home_team_id')
counts=[x[0] for x in c.fetchall()]
if counts:
    print(f'Matches per team: Mean {np.mean(counts):.2f}, Median {np.median(counts)}, Max {np.max(counts)}')
