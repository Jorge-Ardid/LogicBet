@echo off
echo 1. Iмпорт всiх матчiв АПЛ (25-26) з RAW_DATA...
python python\import_all_history.py

echo.
echo 2. Перерахунок рейтингiв Elo та форми на основi нових даних...
python python\recalculate_all_elo.py

echo.
echo === ГОТОВО! Тепер перевiрте профiлi в Godot ===
pause
