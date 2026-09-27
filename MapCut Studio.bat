@echo off
chcp 65001 >nul
rem Cift tiklayarak MapCut Studio arayuzunu acar (Windows).
cd /d "%~dp0scripts"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 gui.py
) else (
    python gui.py
)
if errorlevel 1 (
    echo.
    echo Uygulama hata ile kapandi. Kurulum yapilmadiysa once kurulum_windows.bat dosyasini calistir.
    pause
)
