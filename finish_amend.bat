@echo off
cd /d C:\temp\logicbet_push
set GIT_PAGER=cat
echo --- removing junk from tracking ---
git rm --cached -q check_export.py do_cherry.bat 2>nul
if exist check_export.py del /q check_export.py
if exist do_cherry.bat del /q do_cherry.bat
echo --- restoring MY data files (correct is_hit) from a4db383 ---
git checkout a4db383 -- godot_app/logicbet.db python/logicbet_export.json data/blackbox_history_backup.json 2>&1
echo --- staging ---
git add -A
echo --- amending ---
git commit --amend --no-edit 2>&1
echo --- HEAD stat ---
git --no-pager show --stat --oneline HEAD 2>&1
echo --- files present check ---
git --no-pager ls-tree -r --name-only HEAD 2>&1
echo --- push ---
git push origin main 2>&1
exit /b 0
