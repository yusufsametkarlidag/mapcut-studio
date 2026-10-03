# HeyGen akışı — gözlem notları (2026-10-03, kullanıcıyla birlikte)

Taslak notlar; /hikaye yeteneği yazılırken kullanılacak.

1. `https://app.heygen.com/home` → sol menü **"Scene by scene"** → AI Studio (`/home/studio`).
2. **Get started → "New video"** kartı → editör açılır: `https://app.heygen.com/create-v4/draft?vt=l&panel=scene`
   - Editör, en son kullanılan avatar ve sesle açılıyor (ör. avatar ve ses son
     kullanılanlar, Motion Engine "Avatar IV", Layout "Original").
   - Sol: Script paneli — textbox placeholder "Type your script or use '/' for commands",
     yanında "Upload audio", "Script Writer".
   - Sağ üst: **Generate** düğmesi (script boşken pasif).
3. Avatar seçimi: sağ paneldeki avatar adına tıkla, sonra tekrar tıkla → **"Choose Avatar"** penceresi
   (`subPanel=looks`). Sekmeler: Recently Used / **My Avatars** / Public Avatars; **Search** kutusu;
   kart düğmesi avatar adıyla. Avatar adı ayarlardan gelmeli (kullanıcıya göre değişir).
3b. **Motion Engine → "Avatar III" seçilmeli** (kullanıcının kuralı; script yapıştırmadan önce).
   Sağ panel "Motion Engine" açılır menüsü (şu an "Avatar IV" düğmesi) → menuitem'ler:
   "Avatar V" (Premium), "Avatar IV" (Premium), **"Avatar III"** ("Applies lip sync. Unlimited usage.").
   Avatar III sınırsız kullanım → kredi harcamıyor olabilir; Generate penceresinde doğrulanacak.
   ⚠️ Motion Engine **her yeni videoda Avatar IV'e dönüyor** — her seferinde Avatar III'e alınmalı.
4. Script: sol paneldeki editör `div.tiptap.ProseMirror` (contenteditable). Yapıştırınca proje kaydedilip
   URL `create-v4/<proje-id>?vt=l&panel=scene` oluyor.
   ⚠️ **Yazarak (type) girilen metin kayda geçmiyor** (soluk görünür, Generate pasif kalır). Doğru yol:
   metni `pbcopy` ile panoya koy → "Type your script or use '/' for commands" satırına tıkla → **Cmd+V**.
   Yanındaki **"Script Writer"** düğmesine tıklama (AI script istem kutusu açıyor). Yapıştırınca Generate aktifleşir.
5. Sağ üst **Generate** → **"Generate Video"** penceresi:
   Title (varsayılan "Untitled Video" — vidN / başlık yazılmalı), Resolution **1080p**, Format **MP4**,
   Save to **My Projects**, HeyGen Watermark **Off** → **Cancel / Submit**.
   ⚠️ Submit'ten önce Motion Engine düğmesinin "Avatar III" yazdığı doğrulanmalı (ilk denemede
   Avatar IV'te kalmıştı).
   ✅ **Kredi testi (2026-10-03):** Avatar III ile üretim öncesi ve sonrası bakiye değişmedi.
   Avatar III kredi harcamıyor → Submit otomatik yapılabilir. Bakiye: sol alttaki profil → "Credits  N left".
6. Submit (Avatar III ile) → otomatik olarak **Projects** sayfasına (`/projects`, "My Projects") gidiyor.
   Yeni kart en üstte "TODAY" altında: başlık + "NN% Ready" ilerleme yazısı; bitince süre rozeti
   (ör. "15m 56s") çıkıyor. Kart metni: "<Title> • just now • AI Studio".
7. İndirme: bitmiş karta **sağ tık** → bağlam menüsü: Go to Video / Change Thumbnail / **Download** /
   Share / Rename / Move / Trash → **Download**. (Ardından kalite penceresi çıkıp çıkmadığı doğrulanacak.)
   İnen dosya ~/Downloads'a gelir → vidN/avatar.mp4 olarak alınır, süresi ölçülür (story_tools.import_avatar).
