# 🎬 MapCut Studio

**Fikirden bitmiş videoya.** Anlatımlı belgesel/hikâye videoları (avatar seslendirme + yüzlerce görsel +
sinematik B-roll) için uçtan uca üretim aracı. **macOS ve Windows**'ta çalışır.

> ⚖️ **Lisans:** [PolyForm Noncommercial 1.0.0](LICENSE.md) — kişisel ve ticari olmayan kullanım
> **ücretsiz ve serbesttir**. **Ticari kullanım, satış veya ücretli hizmet olarak sunmak yasaktır.**
> Ticari kullanım izni için proje sahibiyle iletişime geçin. Ayrıntılar: [Lisans](#️-lisans-ve-kullanım-koşulları).

---

## İçindekiler
- [Ne yapar?](#ne-yapar)
- [Kurulum](#kurulum) — [macOS](#-macos) · [Windows](#-windows-10--11)
- [İlk ayarlar](#ilk-ayarlar)
- [Adım adım kullanım](#adım-adım-kullanım)
- [Zaman haritası formatı](#zaman-haritası-formatı)
- [Dosya adlandırma kuralları](#dosya-adlandırma-kuralları)
- [Render ayarları](#render-ayarları)
- [Komut satırı](#komut-satırı)
- [Proje yapısı](#proje-yapısı)
- [Lisans ve kullanım koşulları](#️-lisans-ve-kullanım-koşulları)

---

## Ne yapar?

Bir video dört aşamada üretilir; MapCut Studio her aşamayı ya otomatikleştirir ya da kolaylaştırır:

| Aşama | Ne olur | MapCut Studio'nun katkısı |
|---|---|---|
| **1. Hikâye** | Fikir → başlık, açıklama, script → avatar seslendirmesi (HeyGen) → zaman haritası | **/hikaye** (Claude Code ile, opsiyonel): claude.ai sohbetinden 3 fikir ister, seçtirir, paketi ve scripti alır, HeyGen'de avatarı üretip indirir, haritayı aldırıp **kontrol eder** |
| **2. Görseller** | Haritadaki ~150–170 görsel promptu Google Flow'da üretilir | Flow mesajını hazırlar; **otomatik devam** betiği her partı kendisi onaylar, başarısızları yeniden ürettirir, adları düzeltir; indirilen zip'i **doğru numaralarla** klasöre koyar ve eksikleri söyler |
| **3. Videolar** | 10 adet 5 saniyelik B-roll klip | Aynı sistem; sesler otomatik silinir |
| **4. Render** | Hepsi saniyesi saniyesine kurgulanır | Crossfade, Ken Burns hareketi, film efekti, ses normalizasyonu, kelime kelime altyazı; tek tuş |

Elle yapıldığında saatler süren hizalama ve takip işi, birkaç tıklamaya iner.

```
 claude.ai ──► script ──► HeyGen ──► avatar.mp4 ──► claude.ai ──► TIMELINE_MAP.md
                                                                    │
                    Google Flow ◄── görsel/video promptları ◄───────┘
                         │
                         ▼
          görseller/  +  videolar/  +  avatar.mp4  ──►  MapCut render  ──►  final.mp4
```

---

## Kurulum

Uygulamanın kendisi ücretsizdir. Kullandığı servisler (Claude, HeyGen, Google Flow) kendi
abonelikleriyle çalışır; MapCut Studio bunlar için **ekstra API ücreti gerektirmez**.

### 🍎 macOS

```bash
brew install python@3.10 python-tk@3.10 ffmpeg-full
git clone https://github.com/yusufsametkarlidag/mapcut-studio.git
```

- `ffmpeg-full` şarttır (normal `ffmpeg`'te altyazı yakma yok). Altyazı için gereken `whisper-cpp` onunla gelir.
- **Açmak için:** Finder'da `VideoEditStudio.command` dosyasına çift tıkla (ilk seferde: sağ tık → Aç).

### 🪟 Windows 10 / 11

1. GitHub sayfasında **Code → Download ZIP** → bir klasöre çıkar.
2. **`kurulum_windows.bat`**'a çift tıkla — Python, ffmpeg ve altyazı için whisper.cpp kurulur (bir kere).
3. **`MapCut Studio.bat`** ile aç. Arkadaki siyah pencereyi kapatma.

> SmartScreen "bilgisayarınızı korudu" derse: **Ek bilgi → Yine de çalıştır**.

Video kodlaması ekran kartına göre otomatik seçilir: Mac'te VideoToolbox; Windows'ta NVIDIA (NVENC),
Intel (QuickSync) veya AMD (AMF), hiçbiri yoksa işlemci (libx264).

### Opsiyonel: Claude Code (hikâye otomasyonu için)

`/hikaye` otomasyonu için [Claude Code](https://claude.com/claude-code) ve tarayıcıda
**Claude in Chrome** eklentisi gerekir. Normal bir Claude aboneliği yeterlidir. Kullanmak istemeyen
hikâye aşamasını eskisi gibi elle yapar; uygulamanın geri kalanı aynen çalışır.

> ⚠️ `/hikaye` ve Flow otomatik devam betiği, üçüncü taraf sitelerde (claude.ai, HeyGen, Google Flow)
> **senin hesabınla** işlem yapar. Bu servislerin kullanım koşulları otomasyonu kısıtlayabilir (HeyGen'inki
> açıkça yasaklar). Bu araçları kullanmak **kendi sorumluluğundadır**; düşük hacimde kullan ve bir uyarı
> görürsen bırak. Uygulamanın çekirdeği (harita, kontroller, render) bu servislere bağlı değildir.

---

## İlk ayarlar

Uygulamada **Video Asistanı… → Hikâye & Harita → Ayarlar…**:

| Ayar | Örnek | Açıklama |
|---|---|---|
| Ana klasör | `~/Desktop/Videolar` | Her video için `vid1`, `vid2`… klasörleri burada açılır |
| claude.ai sohbet linki | `https://claude.ai/chat/…` | Hikâyelerin yazıldığı sohbet; her video aynı sohbette devam eder |
| Fikir mesajı | `3 başlık fikir ver` | Sohbete gönderilen ilk mesaj |
| Harita mesajı | `avatar seslendirmem {DK} dakika {SN} saniye …` | `{DK}` `{SN}` `{TOPLAM_SN}` avatar süresiyle doldurulur |
| HeyGen avatar / ses | kendi avatarının adı | HeyGen → My Avatars'taki ad |
| Motion Engine | `Avatar III` | Avatar III kredi harcamaz |

Ayarlar `ayarlar.json` dosyasında tutulur (kişiseldir, git'e girmez; örnek: `ayarlar.ornek.json`).

---

## Adım adım kullanım

Ana pencerede **Video Asistanı…** düğmesine bas.

### 1. Hikâye ve harita
- **Otomatik (Claude Code ile):** **Claude Code ile hikâye üret** → Claude Code'da `/hikaye`
  (VS Code eklentisinde mesajda `@browser` olmalı). Claude Code fikirleri sana gösterip seçimini sorar;
  gerisini (paket, script, HeyGen, harita, kontrol) kendisi yapar. Talimatlar: `.claude/skills/hikaye/SKILL.md`.
- **Elle:** Hikâyeni her zamanki gibi yazdır; HeyGen videosunu **Avatar videosunu seç** ile al (süresi
  otomatik ölçülür); haritayı `vidN` klasörüne koyup **Haritayı kontrol et**'e bas.

Harita kontrolü şunlara bakar: toplam süre avatarla saniyesi saniyesine tutuyor mu, her görselin ve
her videonun promptu var mı, zaman tablosunda boşluk/çakışma var mı.

### 2. Görseller (Google Flow)
1. **Flow** sekmesi → **Klasör Seç** (`vidN`).
2. **① Görsel mesajını kopyala** → Flow'da **Yeni proje** (Ajan modu) → yapıştır → gönder.
3. **② Oto-devam kodunu kopyala** → Flow sekmesinde konsolu aç (Mac: `Cmd+Option+J`,
   Windows: `Ctrl+Shift+J`) → yapıştır → Enter. *(İlk seferde Chrome uyarırsa konsola `allow pasting` yaz.)*
   Sol altta **Flow Oto-Devam** paneli çıkar; partları kendisi onaylar, başarısız ya da yanlış
   adlandırılmış görselleri düzelttirir.
4. Panel **Bitti** deyince: Flow ızgara ayarından boyutu **K** yap → hepsini sürükleyerek seç → sağ tık →
   **İndir** → **③ İndirilenleri al → görseller**. Eksik/çift numara varsa listelenir.

### 3. Videolar
Aynı adımlar, **Videolar** bölümüyle. Kredi onaylarını kod otomatik verebilir (en fazla 10).
Videoların sesi içe aktarılırken silinir.

### 4. Render
1. Ana pencerede **Proje Klasörü Seç / Oluştur** (render çıktısının yazılacağı klasör).
2. Video Asistanı → **Görselleri + videoları render projesine aktar** (harita + avatar da gelir).
3. Ayarları seç → **Test Render** ile ilk dakikalara bak → **Tam Render**. Çıktı `output/` klasöründe.

---

## Zaman haritası formatı

`TIMELINE_MAP.md` dört bölümden oluşur:

1. `## 1. AVATAR TALKING HEAD CUE SHEET` — avatar blokları (A1 her zaman 0:00–0:20)
2. `## 2. …` — video promptları, her biri `**V1 — Başlık**` ile başlar
3. `## 3. GÖRSEL PROMPT HARİTASI` — partlar `### Görsel #a–#b (…)`, her görsel `- #N: …`
4. `## 4. TIMELINE ENTEGRASYON PLANI` — kurgu tablosu:

```markdown
| Sıra | Zaman | Süre | İçerik |
|---|---|---|---|
| 1 | 0:00 – 0:20 | 20s | **A1 (Avatar)** — Açılış |
| 2 | 0:20 – 0:35 | 15s | Görsel #1 → #3 (Giriş) |
| 3 | 0:35 – 0:40 | 5s  | **V1** (Yağmurlu sokak) |
```

- `**A1 (Avatar)**` → avatar videosunun **aynı zaman aralığı** ekrana gelir; ses baştan sona avatardandır.
- `**V1**` → `videolar/` içindeki 1 numaralı video.
- `Görsel #4 → #30` → bu görseller satırın süresine eşit bölünür.

## Dosya adlandırma kuralları

Görseller ve videolar **dosya adındaki ilk sayıya** göre sıralanır (sayısal: `#2` < `#10` < `#100`).

- ✅ `Görsel_#12_20261003.jpeg`, `Vid3_—_Başlık.mp4`
- ❌ Numarasız adlar (`image (3).png`, `download.jpg`)

Flow'dan otomatik devam koduyla üretilen dosyalar bu kurala zaten uyar. Klasör seçildiğinde uygulama
eksik, çift ve numarasız dosyaları listeler.

## Render ayarları

- **Görünüm:** Modern (sade grain) · Vintage 1 · Vintage 2 — her biri Hafif/Orta/Güçlü.
- **Geçiş çeşitliliği:** geçişlerin çoğu fade, ~%20'si hafif kaydırma.
- **Ken Burns:** görsellerde yavaş kayma hareketi.
- **Letterbox, vinyet, sıcak ton, ses normalizasyonu (loudnorm).**
- **Otomatik altyazı:** whisper.cpp ile kelime kelime vurgulu (CapCut/TikTok tarzı); model ilk
  kullanımda indirilir (75 MB – 1.5 GB).

## Komut satırı

```bash
python3 scripts/render.py --project-dir <proje> --test          # Windows: python3 yerine py
python3 scripts/render.py --project-dir <proje> --style vintage1 --captions
python3 scripts/check_assets.py <vidN>/görseller --map <vidN>/TIMELINE_MAP.md
python3 scripts/story_tools.py kontrol <vidN>/TIMELINE_MAP.md <vidN>
python3 scripts/flow_tools.py al gorsel <vidN> [zip …]
```

İleri seviye: ffmpeg/whisper/encoder `MAPCUT_FFMPEG`, `MAPCUT_FFPROBE`, `MAPCUT_WHISPER`,
`MAPCUT_ENCODER` ortam değişkenleriyle elle seçilebilir.

## Proje yapısı

```
VideoEditStudio.command      # macOS başlatıcı
MapCut Studio.bat            # Windows başlatıcı
kurulum_windows.bat          # Windows tek seferlik kurulum
ayarlar.ornek.json           # örnek kullanıcı ayarları (kendi ayarların: ayarlar.json)
scripts/
  gui.py                     # ana pencere (render)
  flow_gui.py                # Video Asistanı (hikâye/harita, Flow, ayarlar)
  render.py                  # 3 aşamalı ffmpeg render motoru
  parse_timeline.py          # TIMELINE_MAP.md → kurgu listesi
  story_tools.py             # vidN klasörü, avatar süresi, harita kontrolü
  flow_tools.py              # Flow mesajları, zip içe aktarma
  check_assets.py            # eksik/çift/numarasız dosya kontrolü
  captions.py                # whisper.cpp → karaoke altyazı
  platform_tools.py          # macOS/Windows farkları (ffmpeg, encoder, whisper)
  settings.py                # ayarlar.json
flow/flow_oto_devam.js       # Flow otomatik devam betiği (tarayıcı konsolu)
.claude/skills/hikaye/       # /hikaye Claude Code yeteneği + ekran notları
```

---

## ⚖️ Lisans ve kullanım koşulları

Copyright (c) 2026 [yusufsametkarlidag](https://github.com/yusufsametkarlidag).

Bu proje **[PolyForm Noncommercial 1.0.0](LICENSE.md)** ile lisanslanmıştır:

- ✅ Kişisel kullanım, öğrenme, deneme, kendi videoların için kullanma — **serbest ve ücretsiz**.
- ✅ Ticari olmayan amaçla değiştirme ve paylaşma — lisans dosyası ve telif notu korunarak.
- ❌ **Ticari kullanım**: uygulamayı veya türevlerini satmak, ücretli hizmet/abonelik olarak sunmak,
  bir ürüne gömüp ticari olarak dağıtmak — **yasaktır** (ayrı yazılı izin gerekir).
- ❌ Telif notunu kaldırarak kendi eseriymiş gibi yayınlamak.

**Üçüncü taraf servisler:** Claude, HeyGen ve Google Flow'u kullanırken her birinin kendi kullanım
koşulları ve içerik politikaları geçerlidir. MapCut Studio bu servislerin kurallarını aşmak için
tasarlanmamıştır (ör. Flow'un tanınmış kişi politikasına takılan üretimler zorlanmaz, yüzsüz olarak
yeniden yorumlatılır). Üretilen içeriğin sorumluluğu kullanıcıya aittir.
