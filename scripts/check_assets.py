#!/usr/bin/env python3
# MapCut Studio — Copyright (c) 2026 yusufsametkarlidag. PolyForm Noncommercial 1.0.0 lisanslıdır: ticari kullanım yasaktır. Ayrıntı: LICENSE.md
"""
Indirilen gorsel/video klasorunun numaralandirmasini kontrol eder:
  - numarasiz (isimlendirilmemis) dosya var mi
  - ayni numaradan iki dosya var mi
  - 1..beklenen arasinda eksik numara var mi
  - beklenenden buyuk numara var mi

Dosya numarasi, dosya adindaki ILK sayidir:
  "Görsel_#12_20260924191427.jpeg" -> 12,  "Vid3_—_Kayıt_tuşu.mp4" -> 3

Kullanim:
    python3 check_assets.py <klasor> --expected 159
    python3 check_assets.py <klasor> --project-dir /path/to/proje   (beklenen sayi edl.json'dan)
    python3 check_assets.py <klasor> --map /path/to/TIMELINE_MAP.md   (beklenen sayi haritadan)
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mov"}
_FIRST_NUM_RE = re.compile(r"\d+")


def file_number(p: Path):
    m = _FIRST_NUM_RE.search(p.stem)
    return int(m.group()) if m else None


def _ranges(nums):
    """[3,4,5,9] -> '#3–#5, #9'"""
    out = []
    nums = sorted(nums)
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(f"#{nums[i]}" if i == j else f"#{nums[i]}–#{nums[j]}")
        i = j + 1
    return ", ".join(out)


def check_numbering(files, expected=None):
    """Sorun listesi dondurur (bossa her sey yolunda)."""
    by_num = defaultdict(list)
    unnamed = []
    for f in files:
        n = file_number(f)
        if n is None:
            unnamed.append(f.name)
        else:
            by_num[n].append(f.name)

    problems = []
    if unnamed:
        shown = ", ".join(unnamed[:5]) + (f" … (+{len(unnamed) - 5})" if len(unnamed) > 5 else "")
        problems.append(f"Numarasız (isimlendirilmemiş) {len(unnamed)} dosya: {shown}")
    dups = {n: names for n, names in by_num.items() if len(names) > 1}
    if dups:
        problems.append(f"Aynı numaradan birden fazla dosya: {_ranges(dups)}")
    if expected:
        missing = [n for n in range(1, expected + 1) if n not in by_num]
        if missing:
            problems.append(f"Eksik {len(missing)} dosya: {_ranges(missing)}")
        extra = [n for n in by_num if n > expected or n < 1]
        if extra:
            problems.append(f"Haritada olmayan numaralar (beklenen 1–{expected}): {_ranges(extra)}")
    elif by_num:
        top = max(by_num)
        missing = [n for n in range(1, top + 1) if n not in by_num]
        if missing:
            problems.append(f"Numaralarda boşluk var: {_ranges(missing)}")
    return problems


def list_media(folder: Path, exts):
    return [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts]


def main():
    ap = argparse.ArgumentParser(description="Gorsel/video numaralandirma kontrolu")
    ap.add_argument("folder")
    ap.add_argument("--expected", type=int, default=None)
    ap.add_argument("--project-dir", default=None, help="beklenen sayiyi <proje>/edl.json'dan al")
    ap.add_argument("--map", default=None, help="beklenen sayiyi TIMELINE_MAP.md'den al")
    ap.add_argument("--videos", action="store_true", help="gorsel yerine video klasoru kontrol et")
    args = ap.parse_args()

    folder = Path(args.folder)
    files = list_media(folder, VIDEO_EXTS if args.videos else IMAGE_EXTS)
    expected = args.expected
    if expected is None and args.map:
        import parse_timeline
        summary = parse_timeline.build_edl(Path(args.map))["summary"]
        expected = summary["video_segments" if args.videos else "total_images"]
    if expected is None and args.project_dir:
        summary = json.loads((Path(args.project_dir) / "edl.json").read_text(encoding="utf-8"))["summary"]
        expected = summary["video_segments" if args.videos else "total_images"]

    print(f"{folder}: {len(files)} dosya" + (f", beklenen {expected}" if expected else ""))
    problems = check_numbering(files, expected)
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        sys.exit(1)
    print("  ✅ Hepsi numaralı, eksik ya da çift yok.")


if __name__ == "__main__":
    main()
