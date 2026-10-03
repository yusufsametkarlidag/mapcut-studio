---
name: hikaye
description: Yeni bir video için hikâye aşamasını uçtan uca yürütür — claude.ai sohbetinden 3 başlık fikri alır, kullanıcıya seçtirir, paketi ve scripti alır, HeyGen'de avatar videosunu üretip indirir, avatar süresiyle haritayı (TIMELINE_MAP) aldırıp kontrol eder. Kullanıcı "/hikaye", "yeni video başlat", "hikâye üret" dediğinde kullan. Chrome (Claude in Chrome) gerektirir.
---

# /hikaye — fikirden kontrol edilmiş haritaya

Bu yetenek MapCut Studio (VideoEditStudio) projesinin parçasıdır. Uygulamanın kullanıcıya özel
ayarları `ayarlar.json` dosyasındadır; **hiçbir kanal/proje adını varsayma, her şeyi ayarlardan oku.**
Tarayıcı işleri Claude in Chrome araçlarıyla yapılır (VS Code'da mesajda `@browser` gerekir).

Ayrıntılı ekran notları (hangi düğme nerede, bilinen tuzaklar):
- `.claude/skills/hikaye/claude_ai_notlar.md`
- `.claude/skills/hikaye/heygen_notlar.md`

**İşletim sistemi farkları:** macOS'ta pano `pbcopy` / `pbpaste`, kısayol **Cmd**; Windows'ta (PowerShell)
`Get-Clipboard` / `Set-Clipboard`, kısayol **Ctrl** (ör. Cmd+V yerine Ctrl+V). İndirilenler: `~/Downloads`
(Windows'ta `%USERPROFILE%\Downloads`).

Yardımcı komutlar (`P` = Python 3.10+; macOS'ta `/opt/homebrew/bin/python3.10`, Windows'ta `py`):
```
P scripts/settings.py                                  # ayarları göster
P scripts/story_tools.py yeni-klasor                   # sıradaki vidN klasörü → yolunu yazar
pbpaste | P scripts/story_tools.py kaydet <vid> <ad>   # panodaki metni kaydet (Windows: Get-Clipboard -Raw | py …)
P scripts/story_tools.py avatar <vid> <indirilen.mp4>  # avatar.mp4 + süre (DK / SN)
P scripts/story_tools.py harita-mesaji <vid>           # harita isteme mesajı (süre dolu)
P scripts/story_tools.py kontrol <harita.md> <vid>     # haritayı kontrol et
```

## 0. Hazırlık
1. Ayarları oku. `claude_sohbet_url` boşsa ya da `heygen.avatar` boşsa kullanıcıya sor, cevabı
   `ayarlar.json`'a kaydet (scripts/settings.py içindeki `save`) ve devam et.
2. `tabs_context_mcp` ile sekmeleri al, işin için **yeni sekmeler** aç (kullanıcının sekmelerine dokunma).
3. `yeni-klasor` ile vidN klasörünü oluştur ve kullanıcıya söyle.

## 1. Fikir ve seçim (claude.ai)
1. `claude_sohbet_url`'ye git. **Her video aynı sohbette devam eder** — yeni sohbet açma.
2. `fikir_mesaji`'ni sohbete gönder ("3 başlık fikir ver" gibi). Cevabın bitmesini bekle
   (gönder düğmesi tekrar görünene / yazma göstergesi kaybolana kadar; get_page_text ile kontrol et).
3. Gelen fikirleri **kullanıcıya bu konuşmada** kısaca listele (başlık + bir satır hook) ve hangisini
   istediğini sor. Kullanıcı seçene kadar ilerleme.
4. Seçilen fikrin bloğunu (cevaptaki haliyle: formül/başlık/hook/isimler) **aynen** sohbete gönder.

## 2. Paket ve script
1. claude.ai scripti ve üretim paketini yazana kadar bekle (uzun sürebilir; birkaç dakikada bir kontrol et).
2. Paket genelde bir artifact olarak gelir → **Open**. Artifact cross-origin iframe'dir, DOM'dan okunmaz:
   ilgili bölümün **Kopyala** düğmesine gerçek tıklama yap, sonra panoyu oku.
   - Script ("Anlatım metni" / narration) → `pbpaste | … kaydet <vid> SCRIPT.txt`
   - Başlık + açıklama (+ varsa thumbnail promptu) → `PAKET.md` olarak kaydet.
   Paket farklı biçimdeyse (artifact yoksa) scripti sohbetten tek parça kopyalayacak yolu bul; gerekirse
   claude.ai'den scripti tek bir kod bloğunda vermesini iste. Script uzunluğunu kontrol et (boş/eksik olmasın).

## 3. HeyGen avatar videosu
`heygen_notlar.md`'deki adımlar. Özet:
1. app.heygen.com → **Scene by scene** (AI Studio) → **New video**.
2. Avatar `heygen.avatar` değilse: avatar adına tıkla → **Choose Avatar** → My Avatars → ara → seç.
   Ses `heygen.ses` ile uyuşmuyorsa kullanıcıya söyle.
3. **Motion Engine**'i her seferinde `heygen.motion_engine`'e (Avatar III) al — editör Avatar IV'e dönüyor.
4. Scripti **yazma**: `pbcopy < <vid>/SCRIPT.txt` (Windows: `Get-Content -Raw <vid>\SCRIPT.txt | Set-Clipboard`),
   "Type your script…" satırına tıkla, **Cmd+V / Ctrl+V**
   ("Script Writer" düğmesine tıklama). Generate aktifleşmeli.
5. **Generate** → Title: `<vidN> — <video başlığı>`; 1080p / MP4 / Watermark Off.
   Submit'ten hemen önce Motion Engine düğmesinin `heygen.motion_engine` yazdığını doğrula.
   `heygen.otomatik_submit` false ise Submit'i kullanıcıya bırak.
6. Projects sayfasında videonun yüzdesini izle (≈20 dk; aralıkları geniş tut, gereksiz kontrol yapma).
   Bitince karta sağ tık → **Download**. İnen dosyayı `avatar` komutuyla vidN'e al → süre (DK, SN).

## 4. Harita
1. `harita-mesaji <vid>` çıktısını aynı claude.ai sohbetine gönder.
2. Harita dosyası gelince dosya kartındaki **Download** → `~/Downloads/TIMELINE_MAP*.md` → vidN'e taşı.
3. `kontrol <vid>/TIMELINE_MAP….md <vid>` çalıştır. Sorun varsa sorunları claude.ai'ye yazıp
   düzelttir, yeni dosyayı indirip tekrar kontrol et (en fazla 2 tur; sonra kullanıcıya bırak).

## 5. Bitiş
Kullanıcıya kısa özet ver: vidN yolu, başlık, avatar süresi, harita özeti (görsel/video sayısı).
Sonraki adım: uygulamada **Video Asistanı → Flow** sekmesi (görseller ve videolar).
Açtığın sekmeleri kapat (kullanıcı tutmak istemedikçe). İndirilenler'de bıraktığın geçici dosyaları
çöpe taşı.

## Kurallar
- claude.ai sohbetinde kullanıcının adına yalnızca bu akıştaki mesajları gönder; sohbetin eski içeriğini
  değiştirme/silme.
- Kredi/ücret çıkaran bir adım (Avatar III dışı motor, ücretli çözünürlük vb.) varsa durup sor.
- Bir adım 2–3 denemede olmuyorsa ısrar etme; ne denediğini söyleyip kullanıcıya sor.
