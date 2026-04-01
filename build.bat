@echo off
chcp 65001 >nul
echo ── 의뢰파일 폴더 생성 EXE 빌드 ──
echo.

pip install pyinstaller >nul 2>&1

pyinstaller --onefile --windowed --name "의뢰파일폴더생성" --add-data "assets;assets" app.py

echo.
echo ──────────────────────────────
echo  빌드 완료!
echo  dist\의뢰파일폴더생성.exe
echo ──────────────────────────────
pause
