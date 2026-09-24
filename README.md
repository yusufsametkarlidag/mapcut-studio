# 🎬 MapCut Studio

**Haritayı ver, videoyu al.** Yüzlerce görsel, B-roll video ve avatar
konuşmasından oluşan uzun belgesel/hikâye videolarını, tek bir zaman
çizelgesi dosyasından (`TIMELINE_MAP.md`) **otomatik olarak** kurgulayan
macOS masaüstü uygulaması.

CapCut'ta 17 dakikalık bir videoya 174 görseli, 10 B-roll klibi ve 6 avatar
bloğunu tek tek sürükleyip saniyesi saniyesine hizalamak saatler sürer.
MapCut Studio bunu tek tuşla yapar: geçişleri, Ken Burns hareketini, film
efektini, ses normalizasyonunu ve kelime kelime vurgulu altyazıyı da ekler.

---

## Ne işe yarar?

YouTube tarzı "anlatımlı hikâye" videoları genelde şu parçalardan oluşur:

| Parça | Açıklama |
|---|---|
| **Avatar** (`avatar.mp4`) | Tüm seslendirmeyi içeren konuşan kafa videosu. Videonun **sesi baştan sona buradan** gelir. |
| **B-roll videolar** (`V1…Vn`) | 5 saniyelik sinematik atmosfer klipleri (Kling, Runway, Luma, Flow vb.). |
| **Görseller** (`#1…#n`) | Hikâyeyi anlatan sabit görseller (Midjourney, FLUX, Flow vb.). |
| **Zaman haritası** (`TIMELINE_MAP.md`) | Hangi saniyede ne görüneceğini söyleyen tablo. |

MapCut Studio bu parçaları alır, haritadaki tabloya göre **birebir aynı
saniyelere** yerleştirir ve bitmiş bir `.mp4` üretir. Avatar sadece haritada
yazan aralıklarda ekranda görünür; diğer zamanlarda görsel/video akarken
avatarın sesi arkada devam eder.

## Nasıl çalışır?

```
TIMELINE_MAP.md ──► parse_timeline.py ──► edl.json (kurgu listesi)
                                             │
  avatar.mp4 + videolar/ + gorseller/ ──────►│
                                             ▼
                                        render.py
          A) Normalize  : her parça 1920×1080 / 30fps klibe çevrilir
                          (görsellere Ken Burns kaydırma eklenir)
          B) Birleştir  : klipler crossfade geçişleriyle zincirlenir
          C) Final      : efekt + altyazı + avatar sesi (loudnorm) → .mp4
```

1. **Harita okunur.** `parse_timeline.py`, markdown dosyasındaki
   `## 4. TIMELINE ENTEGRASYON PLANI` tablosunu okur ve her satırı bir
   kurgu adımına çevirir. Zamanlarda boşluk ya da çakışma varsa, ya da süreler
   tutmuyorsa render'a başlamadan hata verir.
2. **Parçalar hazırlanır.** Her görsel, video ve avatar bloğu aynı
   çözünürlükte ayrı bir klibe dönüştürülür. Geçişlerin "yediği" süre her
   klibe önceden eklenir, böylece crossfade'ler zamanlamayı kaydırmaz.
3. **Birleştirme.** Klipler 8'erli gruplar halinde xfade ile birleştirilir
   (macOS'un açık dosya limitine takılmamak için).
4. **Final.** Film grain, sıcak renk tonu, hafif kamera "nefesi", altyazı ve
   avatarın tam ses kanalı eklenir. Encode, Apple Silicon donanım
   hızlandırmasıyla (VideoToolbox) yapılır.
5. **Doğrulama.** Çıktının süresi harita süresiyle karşılaştırılıp rapor
   edilir.

### Zaman haritası formatı

`TIMELINE_MAP.md` içinde şu başlık ve tablo bulunmalı:

```markdown
## 4. TIMELINE ENTEGRASYON PLANI

| Sıra | Zaman | Süre | İçerik |
|---|---|---|---|
| 1 | 0:00 – 0:20 | 20s | **A1 (Avatar)** — Açılış |
| 2 | 0:20 – 0:35 | 15s | Görsel #1 → #3 (Giriş kurulumu) |
| 3 | 0:35 – 0:40 | 5s  | **V1** (Yağmurlu sokak) |
| 4 | 0:40 – 2:55 | 135s | Görsel #4 → #30 (...) |
```

- `**A1 (Avatar)**` → avatar.mp4'ün **aynı zaman aralığı** ekrana gelir.
- `**V1**` → `videolar/V1.mp4`
- `Görsel #4 → #30` → bu görseller satırın süresine eşit bölünerek sırayla
  gösterilir (135 sn / 27 görsel = her biri 5 sn).

## Kurulum

Sadece **macOS (Apple Silicon)** üzerinde test edildi.

```bash
brew install python@3.10 python-tk@3.10 ffmpeg-full
git clone https://github.com/yusufsametkarlidag/mapcut-studio.git
```

- `ffmpeg-full` şart: normal `ffmpeg` paketinde altyazı yakma (libass) ve
  whisper desteği yok. Uygulama doğrudan
  `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg` yolunu kullanır.
- Altyazı için `whisper-cpp`, `ffmpeg-full` ile birlikte gelir. Seçilen model
  ilk kullanımda otomatik indirilir (75 MB – 1.5 GB).

Ek bir Python paketi gerekmez (sadece standart kütüphane + Tkinter).

## Kullanım

**Açmak için:** Finder'da `VideoEditStudio.command` dosyasına çift tıkla
(ilk seferde: sağ tık → Aç). Terminal'den: `python3.10 scripts/gui.py`

1. **Proje Klasörü Seç / Oluştur.** Her video için ayrı bir klasör. Gerekli
   alt klasörler (`avatar/`, `videolar/`, `gorseller/`, `assets/`, `output/`)
   otomatik oluşturulur.
2. **TIMELINE_MAP.md Seç.** Dosya okunur ve üstte özet gösterilir: toplam
   süre, kaç görsel, kaç video ve kaç avatar bloğu beklendiği.
3. **avatar.mp4 Seç.**
4. **Video Klasörü Seç.** İndirdiğin B-roll'lar `V1.mp4, V2.mp4…` olarak
   kopyalanır.
5. **Görsel Klasörü Seç.** Görseller `gorsel_001, gorsel_002…` olarak
   kopyalanır.
6. **Ayarlar.** Crossfade süresi, görünüm stili, efekt yoğunluğu, sıcak ton,
   Ken Burns, vinyet, letterbox, geçiş çeşitliliği ve ses normalizasyonu.
7. **Altyazı.** Kelime kelime sarı vurgulu (CapCut/TikTok tarzı) otomatik
   altyazı; model boyutu ve dil seçilebilir.
8. **Test Render** (ilk N saniye) ya da **Tam Render.** İlerleme alttaki
   panelde görünür. Bitince süre raporu çıkar ve çıktı `output/` klasörüne
   yazılır.

### ⚠️ Dosya adlandırma (önemli)

Görseller ve videolar **dosya adındaki ilk sayıya göre** sıralanır. Bu
sıralama sayısaldır, alfabetik değildir: `#2`, `#10`'dan önce, `#10` da
`#100`'den önce gelir. Bu yüzden:

- ✅ `Görsel_#1_20260924.jpeg`, `Görsel_#2_...`, … `Görsel_#174_...`
- ✅ `Vid1_—_Yağmurlu_sokak.mp4`, … `Vid10_—_...mp4`
- ❌ Numarasız adlar (`image (3).png`, `download.jpg` …)

Bir numara eksikse (örn. #57 indirilmemiş) sonraki bütün görseller bir kayar.
Uygulama toplam sayı haritayla tutmazsa uyarır; bu uyarıyı görürsen devam
etme, eksik dosyayı bul.

### Görünüm stilleri

- **Modern:** Sallanma yok, sadece hafif film grain.
- **Vintage 1:** Zar zor hissedilen bir kamera "nefesi" ve biraz daha
  belirgin grain.
- **Vintage 2:** Vintage 1'in daha belirgin hali.

Her stil Hafif / Orta / Güçlü yoğunlukla ölçeklenir.

## Komut satırından kullanım

Arayüz olmadan da çalıştırılabilir. Otomasyon ya da toplu render için:

```bash
python3.10 scripts/parse_timeline.py --project-dir ~/Videolar/proje1
python3.10 scripts/render.py --project-dir ~/Videolar/proje1 --test
python3.10 scripts/render.py --project-dir ~/Videolar/proje1 \
    --style vintage1 --effect-intensity medium \
    --captions --caption-model small.en --caption-lang en
```

Tüm seçenekler için: `python3.10 scripts/render.py --help`

## Proje yapısı

```
VideoEditStudio.command   # çift tıkla → arayüzü açar
scripts/
  gui.py                  # Tkinter masaüstü arayüzü
  parse_timeline.py       # TIMELINE_MAP.md → edl.json
  render.py               # 3 aşamalı ffmpeg render motoru
  captions.py             # whisper.cpp → karaoke tarzı .ass altyazı
```

Bir video projesi klasörü (bu repoya dahil **değil**) şöyle görünür:

```
proje1/
  TIMELINE_MAP.md
  avatar/avatar.mp4
  videolar/V1.mp4 … V10.mp4
  gorseller/gorsel_001.jpeg … gorsel_174.jpeg
  output/final_render.mp4
```
