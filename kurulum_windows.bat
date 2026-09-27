@echo off
chcp 65001 >nul
rem MapCut Studio - Windows kurulumu (bir kere calistirmak yeterli).
rem Python, ffmpeg (tam surum) ve altyazi icin whisper.cpp kurar.
cd /d "%~dp0"

echo [1/3] Python kuruluyor...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements

echo.
echo [2/3] ffmpeg kuruluyor...
winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements

echo.
echo [3/3] Altyazi icin whisper.cpp indiriliyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$d=Join-Path (Get-Location) 'tools\whisper';" ^
  "New-Item -ItemType Directory -Force $d | Out-Null;" ^
  "$z=Join-Path $env:TEMP 'whisper-bin-x64.zip';" ^
  "Invoke-WebRequest -Uri 'https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.2/whisper-bin-x64.zip' -OutFile $z;" ^
  "Expand-Archive -Force $z $d; Remove-Item $z"
if errorlevel 1 (
    echo whisper.cpp indirilemedi. Altyazi calismaz ama geri kalan her sey calisir.
)

echo.
echo Kurulum bitti. Bu pencereyi kapatip "MapCut Studio.bat" dosyasina cift tikla.
pause
