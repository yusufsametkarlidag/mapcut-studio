#!/usr/bin/env python3
# MapCut Studio — Copyright (c) 2026 yusufsametkarlidag. PolyForm Noncommercial 1.0.0 lisanslıdır: ticari kullanım yasaktır. Ayrıntı: LICENSE.md
"""
Hikâye & harita aşaması yardımcıları (/hikaye Claude Code yeteneği ve uygulama kullanır).

Komut satırı:
  python3 story_tools.py yeni-klasor                 → ana klasörde sıradaki vidN'i oluşturur, yolunu yazar
  python3 story_tools.py kaydet <vidDir> <dosyaAdı>  → stdin'deki metni vidDir/dosyaAdı olarak kaydeder
  python3 story_tools.py avatar <vidDir> <video>     → videoyu vidDir/avatar.mp4 yapar, süresini yazar
  python3 story_tools.py harita-mesaji <vidDir>      → ayarlardaki harita mesajını avatar süresiyle doldurur
  python3 story_tools.py kontrol <harita.md> [<vidDir>] → haritayı kontrol eder (avatar süresiyle kıyaslar)
"""
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import flow_tools  # noqa: E402
import parse_timeline  # noqa: E402
import settings  # noqa: E402
from platform_tools import NO_WINDOW, TEXT_KW, ffprobe_bin  # noqa: E402

PACKAGE_FILE = "PAKET.md"
SCRIPT_FILE = "SCRIPT.txt"
AVATAR_FILE = "avatar.mp4"


# ------------------------------------------------------------ klasör
def _vid_number(p: Path):
    name = unicodedata.normalize("NFC", p.name).casefold().replace("i̇", "i")
    m = re.fullmatch(r"vid(\d+)", name)
    return int(m.group(1)) if m else None


def next_vid_dir(base: Path = None) -> Path:
    """Ana klasördeki en büyük vidN'den sonrakini oluşturur (görseller/ ve videolar/ ile)."""
    base = base or settings.base_dir()
    base.mkdir(parents=True, exist_ok=True)
    nums = [n for p in base.iterdir() if p.is_dir() and (n := _vid_number(p)) is not None]
    d = base / f"vid{max(nums, default=0) + 1}"
    (d / "görseller").mkdir(parents=True, exist_ok=True)
    (d / "videolar").mkdir(exist_ok=True)
    return d


# ------------------------------------------------------------ avatar
def media_duration(path: Path) -> float:
    r = subprocess.run([ffprobe_bin(), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW, **TEXT_KW)
    return float(r.stdout.strip())


def fmt_mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def import_avatar(vid_dir: Path, src: Path) -> int:
    """Avatar videosunu vidN/avatar.mp4 olarak kopyalar, tam saniye cinsinden süresini döndürür."""
    dest = vid_dir / AVATAR_FILE
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return round(media_duration(dest))


def avatar_seconds(vid_dir: Path):
    p = vid_dir / AVATAR_FILE
    return round(media_duration(p)) if p.exists() else None


def map_request(vid_dir: Path) -> str:
    secs = avatar_seconds(vid_dir)
    if secs is None:
        raise FileNotFoundError(f"{vid_dir / AVATAR_FILE} yok; önce avatar videosunu al.")
    return (settings.load()["harita_mesaji"]
            .replace("{DK}", str(secs // 60)).replace("{SN}", str(secs % 60)).replace("{TOPLAM_SN}", str(secs)))


def save_text(vid_dir: Path, name: str, text: str) -> Path:
    p = vid_dir / name
    p.write_text(text.strip() + "\n", encoding="utf-8")
    return p


# ------------------------------------------------------------ harita kontrolü
def validate_map(map_path: Path, expected_seconds=None):
    """(özet, sorunlar) döndürür. Sorun listesi boşsa harita Flow'a ve render'a hazırdır."""
    problems = []
    try:
        edl = parse_timeline.build_edl(map_path)
    except Exception as e:
        return None, [f"Zaman tablosu okunamadı: {e}"]

    s = edl["summary"]
    total = edl["total_duration_seconds"]
    if expected_seconds is not None and abs(total - expected_seconds) > 1:
        problems.append(f"Haritanın toplam süresi {fmt_mmss(total)} ({total} sn), avatar ise "
                        f"{fmt_mmss(expected_seconds)} ({expected_seconds} sn). Fark: {total - expected_seconds:+d} sn.")

    nums = [img["index"] for e in edl["entries"] if e["type"] == "image_block" for img in e["images"]]
    if nums != list(range(1, len(nums) + 1)):
        problems.append("Tablodaki görsel numaraları 1'den başlayıp kesintisiz artmıyor.")

    md = map_path.read_text(encoding="utf-8")
    try:
        sec3 = flow_tools._section(md, 3)
        prompt_nums = {int(n) for n in re.findall(r"^\s*-\s*#(\d+)\s*:", sec3, flags=re.M)}
        missing = sorted(set(range(1, s["total_images"] + 1)) - prompt_nums)
        if missing:
            problems.append(f"Görsel promptu eksik: #{', #'.join(map(str, missing[:15]))}"
                            + (" …" if len(missing) > 15 else ""))
    except ValueError as e:
        problems.append(str(e))
    try:
        sec2 = flow_tools._section(md, 2)
        v_defined = {f"V{n}" for n in re.findall(r"^\*\*V(\d+)\b", sec2, flags=re.M)}
        v_missing = [v for v in s["video_ids"] if v not in v_defined]
        if v_missing:
            problems.append(f"Video promptu eksik: {', '.join(v_missing)}")
    except ValueError as e:
        problems.append(str(e))

    summary = (f"{fmt_mmss(total)} ({total} sn) • {s['total_images']} görsel • "
               f"{s['video_segments']} video • {s['avatar_segments']} avatar bloğu")
    return summary, problems


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(2)
    cmd = a[0]
    if cmd == "yeni-klasor":
        print(next_vid_dir())
    elif cmd == "kaydet" and len(a) == 3:
        p = save_text(Path(a[1]), a[2], sys.stdin.read())
        print(f"{p} ({p.stat().st_size} bayt)")
    elif cmd == "avatar" and len(a) == 3:
        secs = import_avatar(Path(a[1]), Path(a[2]))
        print(f"avatar.mp4 süresi: {fmt_mmss(secs)} ({secs} sn)  DK={secs // 60} SN={secs % 60}")
    elif cmd == "harita-mesaji" and len(a) == 2:
        print(map_request(Path(a[1])))
    elif cmd == "kontrol" and len(a) in (2, 3):
        exp = avatar_seconds(Path(a[2])) if len(a) == 3 else None
        summ, probs = validate_map(Path(a[1]), exp)
        print(summ or "")
        for p in probs:
            print("❌", p)
        if not probs:
            print("✅ Harita hazır.")
        sys.exit(1 if probs else 0)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
