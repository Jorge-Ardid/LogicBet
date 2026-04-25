@echo off
echo --- LOGICBET CLOUD EXPORTER ---
cd /d "%~dp0"
python -c "import sys; sys.path.append('python'); from database import LogicBetDB; from main import export_to_json; db=LogicBetDB(); export_to_json(db)"
echo.
echo ✅ Файл python/logicbet_export.json оновлено актуальними даними!
echo.
echo Тепер завантажте змiни (Push) на GitHub, щоб вони з'явилися в мобiльному додатку.
pause
