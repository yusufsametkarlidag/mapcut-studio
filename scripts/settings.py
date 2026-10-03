#!/usr/bin/env python3
# MapCut Studio — Copyright (c) 2026 yusufsametkarlidag. PolyForm Noncommercial 1.0.0 lisanslıdır: ticari kullanım yasaktır. Ayrıntı: LICENSE.md
"""
Kullanıcıya özel ayarlar (ayarlar.json, uygulama klasöründe; git'e girmez).
Dosya yoksa ayarlar.ornek.json'daki varsayılanlar kullanılır.

  ana_klasor            Video klasörlerinin (vid1, vid2 …) bulunduğu klasör
  claude_sohbet_url     Hikâyelerin yazıldığı claude.ai sohbeti (her video aynı sohbette)
  fikir_mesaji          claude.ai'ye fikir istemek için gönderilen mesaj
  harita_mesaji         Harita isteme mesajı; {DK} {SN} {TOPLAM_SN} yer tutucuları
  heygen.avatar         HeyGen > My Avatars'taki avatar adı
  heygen.ses            Beklenen ses adı (kontrol için)
  heygen.motion_engine  "Avatar III" (kredi harcamıyor) vb.
  heygen.otomatik_submit  true ise Generate > Submit'e otomasyon basar
"""
import json
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
SETTINGS_FILE = APP_DIR / "ayarlar.json"
EXAMPLE_FILE = APP_DIR / "ayarlar.ornek.json"

DEFAULTS = {
    "ana_klasor": str(Path.home() / "Desktop" / "Videolar"),
    "claude_sohbet_url": "",
    "fikir_mesaji": "3 başlık fikir ver",
    "harita_mesaji": "avatar seslendirmem {DK} dakika {SN} saniye, bir önceki videoda yaptığımız tarzda timeline map istiyorum",
    "heygen": {
        "avatar": "",
        "ses": "",
        "motion_engine": "Avatar III",
        "cozunurluk": "1080p",
        "otomatik_submit": True,
    },
}


def _merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load() -> dict:
    data = DEFAULTS
    for f in (EXAMPLE_FILE, SETTINGS_FILE):
        if f.exists():
            data = _merge(data, json.loads(f.read_text(encoding="utf-8")))
    return data


def save(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def base_dir() -> Path:
    return Path(load()["ana_klasor"]).expanduser()


if __name__ == "__main__":
    print(json.dumps(load(), ensure_ascii=False, indent=2))
