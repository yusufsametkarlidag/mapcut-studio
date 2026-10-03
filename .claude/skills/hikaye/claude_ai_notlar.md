# claude.ai akışı — gözlem notları (2026-10-03, kullanıcıyla birlikte)

Taslak notlar; /hikaye yeteneği yazılırken kullanılacak.

- Kullanıcı hikâyelerini bir claude.ai **Project** içinde, **tek ve uzun bir sohbette** yazdırıyor; her yeni
  video aynı sohbette devam ediyor. Sohbet linki `ayarlar.json > claude_sohbet_url`'den gelir.
- Kanal kuralları Project Instructions'da, örnek/rakip içerikler Project Context dosyalarında duruyor
  (kullanıcıya göre değişir; yetenek bunlara dokunmaz).

## Örnek akış (gerçek bir kullanımdan)
1. Kullanıcı: **"3 başlık fikir ver"**
   Claude: "3 Yeni Başlık Fikri (hepsi 100 karakterin altında):" → her biri
   `Formül X` / başlık satırı / `Hook: …` / `İsimler: …`; sonda **"Hangisiyle devam edelim?"**
2. Kullanıcı seçtiği fikri **aynen yapıştırıyor** (Formül + başlık + Hook + İsimler).
   Claude: scripti dosya olarak yazıyor (~15.5k karakter, 15,550–16,500 aralığı hedefi) ve
   **HTML artifact** "<Kanal> · Üretim Paketi · <konu>" üretiyor
   (başlık, açıklama, thumbnail promptları, anlatım metni). Sonda "Ses kaydının süresini paylaşırsan
   Timeline Map dosyasını da çıkarabilirim."
3. Kullanıcı: **"avatar seslendirmem 15 dakika 56 saniye bir önceki videoda yaptığımız tarzda istiyorum time line"**
   Claude: `TIMELINE_MAP_VIDEO<N>_<KONU>.md` dosyasını paylaşıyor (Document·MD, **Download** düğmesi).

## Paket ve harita dosyalarını alma (doğrulandı)
- **Üretim Paketi** sohbette artifact kartı ("<Kanal> · Üretim Paketi · <konu>") → **Open**
  → sağ panel. Panel cross-origin iframe: içeriği DOM'dan okunamaz.
  Bölümler: "Başlık ve açıklama" (Video başlığı, YouTube açıklaması — her birinde **Kopyala**),
  "Thumbnail", "Anlatım metni (ElevenLabs / TTS)" → "Narration script" kutusu + **Kopyala**.
  → **Kopyala**'ya gerçek tıklama + `pbpaste` ile metin alınır (testte paketteki karakter sayısıyla birebir).
- **Harita**: sohbetteki "Timeline map …" dosya kartının **Download** düğmesi → doğrudan
  `~/Downloads/TIMELINE_MAP_VIDEO<N>_<KONU>.md` (aynı adla) iner.
