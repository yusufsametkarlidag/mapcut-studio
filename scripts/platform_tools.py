#!/usr/bin/env python3
"""
Platforma ozel araclarin (ffmpeg, ffprobe, whisper-cli, video encoder,
dosya yoneticisi) tek yerden bulunmasi. macOS'ta eskisi gibi Homebrew
ffmpeg-full + VideoToolbox kullanilir; Windows/Linux'ta PATH'teki ya da
uygulama klasorundeki tools/ altindaki ikililer kullanilir.

Ortam degiskenleriyle elle de secilebilir:
  MAPCUT_FFMPEG, MAPCUT_FFPROBE, MAPCUT_WHISPER, MAPCUT_ENCODER
"""
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = APP_DIR / "tools"

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
EXE = ".exe" if IS_WINDOWS else ""

# Windows'ta alt surecler icin ekstra konsol penceresi acilmasin
NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0

# Windows konsolunun varsayilan kod sayfasi (cp1254) Turkce karakterleri ve
# ffmpeg ciktisini bozmasin diye tum alt surec ciktilari UTF-8 okunur.
TEXT_KW = dict(text=True, encoding="utf-8", errors="replace")


def _winget_candidates(name: str):
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return []
    base = Path(local) / "Microsoft" / "WinGet"
    return [base / "Links" / f"{name}.exe",
            *sorted((base / "Packages").glob(f"Gyan.FFmpeg*/*/bin/{name}.exe"))]


def _find_tool(name: str, env_var: str, mac_path: str) -> str:
    env = os.environ.get(env_var)
    if env:
        return env
    candidates = []
    if IS_MAC:
        candidates.append(Path(mac_path))
    candidates.append(TOOLS_DIR / "ffmpeg" / "bin" / f"{name}{EXE}")
    if IS_WINDOWS:
        candidates += _winget_candidates(name)
    for c in candidates:
        if c.exists():
            return str(c)
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(
        f"HATA: {name} bulunamadı.\n"
        + ("Kurulum: brew install ffmpeg-full" if IS_MAC else
           "Kurulum: Windows'ta kurulum_windows.bat dosyasını çalıştır "
           "(ya da: winget install Gyan.FFmpeg)")
    )


@lru_cache(maxsize=None)
def ffmpeg_bin() -> str:
    # ffmpeg-full: standart 'ffmpeg' formulunde olmayan libass/zoompan/loudnorm
    return _find_tool("ffmpeg", "MAPCUT_FFMPEG", "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")


@lru_cache(maxsize=None)
def ffprobe_bin() -> str:
    return _find_tool("ffprobe", "MAPCUT_FFPROBE", "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe")


def _encoder_works(ffmpeg: str, encoder: str) -> bool:
    # Encoder listede olsa bile (ör. nvenc) uygun GPU yoksa calismaz, o yuzden
    # kucuk bir deneme encode'u yapilir.
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
           "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
           "-c:v", encoder, "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=30, creationflags=NO_WINDOW, **TEXT_KW)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@lru_cache(maxsize=None)
def video_encoder() -> str:
    env = os.environ.get("MAPCUT_ENCODER")
    if env:
        return env
    if IS_MAC:
        return "h264_videotoolbox"
    ff = ffmpeg_bin()
    # NVIDIA -> Intel -> AMD donanim encoder'i, hicbiri yoksa CPU (libx264)
    for enc in ("h264_nvenc", "h264_qsv", "h264_amf"):
        if _encoder_works(ff, enc):
            return enc
    return "libx264"


def video_encode_args(bitrate: str):
    enc = video_encoder()
    args = ["-c:v", enc, "-b:v", bitrate]
    if enc == "libx264":
        args += ["-preset", "veryfast"]
    return args + ["-pix_fmt", "yuv420p"]


@lru_cache(maxsize=None)
def whisper_bin():
    """whisper-cli yolunu dondurur; bulunamazsa None."""
    env = os.environ.get("MAPCUT_WHISPER")
    if env:
        return Path(env)
    if IS_MAC:
        p = Path("/opt/homebrew/opt/whisper-cpp/bin/whisper-cli")
        if p.exists():
            return p
    wdir = TOOLS_DIR / "whisper"
    if wdir.exists():
        for p in sorted(wdir.rglob(f"whisper-cli{EXE}")):
            return p
    found = shutil.which("whisper-cli")
    return Path(found) if found else None


def whisper_model_dir() -> Path:
    brew_dir = Path("/opt/homebrew/opt/whisper-cpp/share/whisper-cpp/models")
    if IS_MAC and brew_dir.exists():
        return brew_dir
    return APP_DIR / "models"


def reveal_in_file_manager(path: Path):
    path = Path(path)
    if IS_MAC:
        subprocess.run(["open", "-R", str(path)])
    elif IS_WINDOWS:
        subprocess.run(["explorer", f"/select,{path}"])
    else:
        subprocess.run(["xdg-open", str(path.parent)])
