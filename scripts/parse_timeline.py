#!/usr/bin/env python3
"""
TIMELINE_MAP.md -> edl.json (Edit Decision List) parayici.

Herhangi bir proje klasoru icin calisir (--project-dir). Proje klasorunun
kok dizininde bir TIMELINE_MAP.md bulunmasi ve icinde
"4. TIMELINE ENTEGRASYON PLANI" basligi altinda bir tablo olmasi beklenir.

Kullanim:
    python3 parse_timeline.py --project-dir /path/to/proje
    python3 parse_timeline.py --project-dir /path/to/proje --md TIMELINE_MAP.md
"""
import argparse
import json
import re
import sys
from pathlib import Path

TABLE_HEADER_RE = re.compile(r"^\|\s*Sıra\s*\|\s*Zaman\s*\|\s*Süre\s*\|\s*İçerik\s*\|")
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$")

TIME_RANGE_RE = re.compile(r"(\d+):(\d{2})\s*[–\-]\s*(\d+):(\d{2})")
DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s")

AVATAR_RE = re.compile(r"\*\*\s*(A\d+)\b")
VIDEO_RE = re.compile(r"\*\*\s*(V\d{1,2})\s*\*\*")
GORSEL_RE = re.compile(r"Görsel\s*#?(\d+)\s*(?:→|->|-)\s*#?(\d+)")


def mmss_to_seconds(mm: str, ss: str) -> int:
    return int(mm) * 60 + int(ss)


def find_table_rows(md_text: str):
    lines = md_text.splitlines()
    section_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## 4.") and "TIMELINE ENTEGRASYON" in line.upper():
            section_start = i
            break
    if section_start is None:
        raise ValueError("'## 4. TIMELINE ENTEGRASYON PLANI' bölümü bulunamadı.")

    rows = []
    in_table = False
    for line in lines[section_start:]:
        stripped = line.strip()
        if not in_table:
            if TABLE_HEADER_RE.match(stripped):
                in_table = True
            continue
        if stripped.startswith("|---") or stripped.startswith("| ---"):
            continue
        if stripped.startswith("|"):
            rows.append(stripped)
        elif in_table and stripped == "":
            continue
        else:
            break
    return rows


def parse_row(row: str):
    m = ROW_RE.match(row)
    if not m:
        return None
    idx, zaman, sure, icerik = m.groups()

    tm = TIME_RANGE_RE.search(zaman)
    if not tm:
        raise ValueError(f"Zaman aralığı çözümlenemedi: {zaman!r} (satır {idx})")
    start_s = mmss_to_seconds(tm.group(1), tm.group(2))
    end_s = mmss_to_seconds(tm.group(3), tm.group(4))

    dm = DURATION_RE.search(sure)
    if not dm:
        raise ValueError(f"Süre çözümlenemedi: {sure!r} (satır {idx})")
    duration = float(dm.group(1))
    if duration.is_integer():
        duration = int(duration)

    computed = end_s - start_s
    if computed != duration:
        raise ValueError(
            f"Satır {idx}: Zaman aralığından hesaplanan süre ({computed}s) "
            f"tablodaki süre ({duration}s) ile uyuşmuyor: {row!r}"
        )

    entry = {
        "row": int(idx),
        "start": start_s,
        "end": end_s,
        "duration": duration,
        "raw_content": icerik,
    }

    av = AVATAR_RE.search(icerik)
    vid = VIDEO_RE.search(icerik)
    gor = GORSEL_RE.search(icerik)

    if av:
        entry["type"] = "avatar"
        entry["clip_id"] = av.group(1)
        entry["source_in"] = start_s
        entry["source_out"] = end_s
    elif vid:
        entry["type"] = "video"
        entry["clip_id"] = vid.group(1)
    elif gor:
        first, last = int(gor.group(1)), int(gor.group(2))
        count = last - first + 1
        if count <= 0:
            raise ValueError(f"Satır {idx}: geçersiz görsel aralığı {gor.groups()}")
        per_image = duration / count
        entry["type"] = "image_block"
        entry["first_index"] = first
        entry["last_index"] = last
        entry["count"] = count
        entry["per_image_duration"] = per_image
        entry["images"] = []
        t = start_s
        for n in range(first, last + 1):
            entry["images"].append(
                {
                    "index": n,
                    "start": round(t, 6),
                    "duration": round(per_image, 6),
                }
            )
            t += per_image
    else:
        raise ValueError(f"Satır {idx}: içerik türü tanınamadı: {icerik!r}")

    return entry


def build_edl(md_path: Path):
    text = md_path.read_text(encoding="utf-8")
    rows = find_table_rows(text)
    if not rows:
        raise ValueError("Tabloda satır bulunamadı.")

    entries = [parse_row(r) for r in rows]
    entries = [e for e in entries if e is not None]

    prev_end = 0
    for e in entries:
        if e["start"] != prev_end:
            raise ValueError(
                f"Satır {e['row']}: zaman çizelgesinde boşluk/çakışma var "
                f"(beklenen başlangıç {prev_end}s, satırda {e['start']}s)"
            )
        prev_end = e["end"]

    total_duration = entries[-1]["end"]

    avatar_clips = [e for e in entries if e["type"] == "avatar"]
    video_clips = [e for e in entries if e["type"] == "video"]
    image_blocks = [e for e in entries if e["type"] == "image_block"]
    total_images = sum(b["count"] for b in image_blocks)
    video_ids = sorted({e["clip_id"] for e in video_clips}, key=lambda v: int(v[1:]))

    edl = {
        "source_md": str(md_path),
        "total_duration_seconds": total_duration,
        "entries": entries,
        "summary": {
            "avatar_segments": len(avatar_clips),
            "video_segments": len(video_clips),
            "video_ids": video_ids,
            "image_blocks": len(image_blocks),
            "total_images": total_images,
        },
    }
    return edl


def main():
    ap = argparse.ArgumentParser(description="TIMELINE_MAP.md -> edl.json parser")
    ap.add_argument("--project-dir", required=True, help="Proje klasörü (TIMELINE_MAP.md burada aranır)")
    ap.add_argument("--md", default="TIMELINE_MAP.md", help="Proje klasörüne göre MD dosya adı")
    ap.add_argument("-o", "--output", default=None, help="Çıktı JSON yolu (varsayılan: <proje>/edl.json)")
    args = ap.parse_args()

    project_dir = Path(args.project_dir)
    md_path = project_dir / args.md
    if not md_path.exists():
        print(f"HATA: {md_path} bulunamadı.", file=sys.stderr)
        sys.exit(1)

    try:
        edl = build_edl(md_path)
    except ValueError as e:
        print(f"HATA: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output) if args.output else project_dir / "edl.json"
    out_path.write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")

    total = edl["total_duration_seconds"]
    s = edl["summary"]
    print(f"EDL yazıldı -> {out_path}")
    print(f"Toplam süre: {total}s")
    print(
        f"Avatar segment: {s['avatar_segments']}, "
        f"Video segment: {s['video_segments']} ({', '.join(s['video_ids'])}), "
        f"Görsel blok: {s['image_blocks']} (toplam {s['total_images']} görsel)"
    )


if __name__ == "__main__":
    main()
