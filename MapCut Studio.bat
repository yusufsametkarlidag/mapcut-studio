@echo off
chcp 65001 >nul
rem MapCut Studio - Copyright (c) 2026 yusufsametkarlidag. PolyForm Noncommercial 1.0.0 lisanslidir: ticari kullanim yasaktir. Ayrinti: LICENSE.md
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
