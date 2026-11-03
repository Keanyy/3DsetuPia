# Kurulum ve sorun giderme

İki şekilde kullanılabilir:

- **3DsetuPia programı** (`3DsetuPia.exe`): Bambu Studio, QIDI Studio, OrcaSlicer ve benzerleriyle
  çalışır, yeni bir 3MF yazar. Çoğu kullanıcı için önerilen yol budur.
- **OrcaSlicer eklentisi** (`ayarci.py`): ayarları doğrudan OrcaSlicer 2.5'in içinde uygular.

---

## 1. Program (3DsetuPia.exe)

### Gereksinimler

- Windows 10 veya 11 (64 bit). Pencere, Windows'un kendi **Edge WebView2** bileşenini kullanır;
  Windows 11'de hazır gelir. Windows 10'da eksikse Microsoft'un sitesinden
  "WebView2 Runtime" kurun.
- Bilgisayarda en az bir slicer: **Bambu Studio**, **QIDI Studio** veya **OrcaSlicer**.
  Yazıcı listesi ve profiller oradan okunur. Kurulu slicer yoksa yalnızca 3MF'teki yazıcı için
  ayar yapılabilir.

### Kurulum

1. GitHub *Releases* sayfasından `3DsetuPia.exe` dosyasını indirin.
2. İstediğiniz klasöre koyun (ör. Masaüstü). Kurulum gerekmez.
3. Çift tıklayın. Windows **"Windows bilgisayarınızı korudu"** derse **Ek bilgi › Yine de
   çalıştır** deyin. Program kod imzası taşımadığı için bu uyarı çıkar.
4. İlk açılışta slicer profilleri okunur ("Profiller okunuyor…"). Bu bir kez biraz sürer
   (Bambu Studio'da yarım dakika kadar); sonraki açılışlar hızlıdır.

> İpucu: 3MF dosyasını doğrudan `3DsetuPia.exe` simgesinin üzerine sürükleyip bırakabilirsiniz;
> program o dosyayla açılır.

### Kullanım

1. **Dosya:** 3MF, STL veya OBJ dosyasını pencereye sürükleyin ya da kutuya tıklayıp seçin.
   - Slicer projesiyse (Bambu/QIDI/Orca ile *Kaydet* denmiş 3MF) yazıcı, işlem profili, tabla ve
     filamentler görünür.
   - Yalnızca model içeriyorsa (STL, CAD'den çıkan 3MF) hedef yazıcıyı seçmeniz istenir.
   - Dilimlenmiş `.gcode.3mf` dosyaları da açılır; çıktı dilimlenmemiş proje olur.
2. **Hangi yazıcıda basılacak?**
   - *Dosyadaki yazıcı (değiştirme)*: ayarlar aynı yazıcı için iyileştirilir.
   - Listeden başka bir yazıcı: proje o yazıcıya taşınır (üreticinin profilleri, yeni tablaya yerleşim).
   - Listede bilgisayarınızdaki slicer'larda kurulu yazıcılar görünür; **Tüm yazıcıları göster…**
     slicer'ın bildiği bütün yazıcıları açar.
3. **Ayarlanacak filament:** birden çok filament varsa modelin en çok kullandığı seçilidir.
   Başka yazıcıya taşırken o yazıcıdaki filament profilini de seçebilirsiniz (varsayılan: otomatik eşleştir).
4. **Öncelik** ve isteğe bağlı **parça ne için?** notu → **Ayarları hazırla**.
5. Önerileri inceleyin; istemediklerinizin işaretini kaldırın.
6. **Yeni 3MF olarak kaydet** → kaydedilecek yeri seçin. Varsayılan ad: `<dosya adı>_ayarci.3mf`.
7. **"… ile aç"** düğmesi dosyayı ilgili slicer'da açar. **Dilimle**'ye basın ve önizlemeyi kontrol edin.

### Programın dosyaları

`%APPDATA%\3DsetuPia` klasöründe:

| Dosya / klasör | İçerik |
|---|---|
| `ayarci_settings.json` | Yapay zekâ ayarları ve API anahtarı (yalnızca bu bilgisayarda) |
| `ayarci_last_run.json` | Son çalıştırmanın ölçümleri, öneriler, uyarılar (anahtar içermez) |
| `ayarci_error.log` | Beklenmeyen hatalar |
| `cache\` | Slicer profillerinin özet önbelleği (silinirse yeniden oluşturulur) |
| `%TEMP%\3DsetuPia-webview` | Pencere bileşeninin geçici verileri (program kapanınca sonraki açılışta temizlenir) |

Programı kaldırmak için `3DsetuPia.exe` dosyasını ve bu klasörü silmeniz yeterli.

---

## 2. Yapay zekâ bağlama (program ve eklenti için aynı)

**AI Ayarı** sekmesi:

1. **Yapay zekâ sağlayıcısı** seçin.
   - Anahtar gerekmeyen sağlayıcılarda (Ollama, LM Studio) anahtar kutusu **gri** olur.
   - Adresi sabit olan sağlayıcılarda adres kutusu **gri** olur; değiştirmeniz gerekmez.
2. Anahtar gerekiyorsa sağlayıcının "anahtar alma sayfası"ndan bir API anahtarı oluşturup yapıştırın.
3. **Bağlantıyı test et** → model listesi gelir; bir model seçin → **Kaydet**.
   (OrcaSlicer eklentisinde ilk seferde Orca bir **izin penceresi** açar: **Evet** deyip aynı
   düğmeye bir kez daha basın.)
4. **Hazırlık durumu** kartındaki tüm noktalar yeşilse hazırsınız. Üstteki rozet "AI: …" olur.

Yapay zekâ bağlamadan da çalışır: "Yapay zekâ yok (yerel kurallar)" seçiliyken öneriler
yerleşik kurallarla hazırlanır.

### Ücretsiz ve internetsiz yapay zekâ: Ollama

1. [ollama.com](https://ollama.com/download) adresinden Ollama'yı kurun.
2. Komut isteminde bir model indirin, ör.: `ollama pull qwen3`
3. AI Ayarı → **Ollama** → Bağlantıyı test et → modeli seçin → Kaydet.

Küçük yerel modeller büyük bulut modelleri kadar isabetli olmayabilir; 3DsetuPia'nın güvenlik
süzgeci yine de tehlikeli değerleri engeller.

---

## 3. Sorun giderme

| Belirti | Çözüm |
|---|---|
| Program açılmıyor, boş beyaz pencere | Windows 10'da "Microsoft Edge WebView2 Runtime" kurun. |
| Antivirüs exe'yi engelledi | Tek dosyalık Python programlarında yanlış alarm olabilir. Dosyayı GitHub Releases'tan indirdiğinizden emin olun ve antivirüste izin verin. |
| Yazıcı listesi boş | Bambu Studio / QIDI Studio / OrcaSlicer kurulu mu? En az bir kez açılıp yazıcı seçilmiş olmalı. "Tüm yazıcıları göster…"i deneyin. |
| "… çok nozullu bir yazıcı" | Başka yazıcıdan H2D/H2C'ye dönüştürme şimdilik yok. Dosyayı Bambu Studio'da açıp yazıcıyı seçin, kaydedin, sonra 3DsetuPia'ya verin. |
| "Şu nesneler bu tablaya sığmıyor" | Nesne yeni yazıcının tablasından büyük. Slicer'da küçültün ya da kesin (Cut). |
| "Nesneler tek tek sığıyor ama hepsi birden sığmıyor" | Slicer'da **A** (Yerleştir) tuşuna basın veya bazı nesneleri yeni plakaya taşıyın. |
| Slicer dosyayı açarken "daha yeni sürümde oluşturuldu" diyor | Slicer'ınızı güncelleyin ya da dosyayı o slicer'ın kendi yazıcı listesinden seçerek oluşturun. |
| "API anahtarı kabul edilmedi" | Anahtarı yeniden yapıştırın, Kaydet, test edin. Sağlayıcı hesabında kredi/ödeme tanımlı mı kontrol edin. |
| "Yerel kurallar kullanıldı" uyarısı | Ağ/anahtar sorununda 3DsetuPia otomatik olarak kurallara döner; uyarı nedeni söyler. |
| Öneri dilimlemede etkisiz | O nesnenin kendine özel ayarı olabilir (3DsetuPia bunları değiştirmez); uyarıya bakın. |

**Hata bildirirken** şunları ekleyin: 3DsetuPia sürümü (AI Ayarı → Hakkında), slicer ve sürümü,
yazıcı, ve `%APPDATA%\3DsetuPia\ayarci_last_run.json` ile varsa `ayarci_error.log`.
Bu dosyalarda API anahtarı **bulunmaz**. Mümkünse 3MF dosyasını da ekleyin.

---

## OrcaSlicer eklentisi

### Sürüm

Eklenti OrcaSlicer **2.5.0-beta veya daha yeni** bir sürüm ister (2.5.0-RC önerilir).
Sürümü **Help › About OrcaSlicer** ile görün. Eski sürümde eklenti açılmaz ve
"2.5.0-beta veya daha yeni gerekiyor" der. (Program bu sınıra tabi değildir; Orca 2.4 projeleriyle de çalışır.)

### Kurulum

1. `ayarci.py` dosyasını indirin (GitHub *Releases*).
2. OrcaSlicer'da **File › Plugins** → **Browse plugins** düğmesinin yanındaki **ok** →
   **Install local plugin** → `ayarci.py`.
3. Listede 3DsetuPia satırında **Activate** kutusunu işaretleyin. İlk etkinleştirmede Orca gerekli
   Python paketlerini (numpy, certifi, anthropic) indirir; bir dakika kadar sürebilir. İzin
   penceresi çıkarsa **Evet** deyin.

### Kullanım

1. Modeli tablaya ekleyin, yazıcıyı ve filamenti her zamanki gibi seçin.
2. **File › Plugins** → 3DsetuPia → **Run**. Panel 3D görünümün sağına yerleşir.
3. Filament ve öncelik → **Ayarları hazırla** → **Seçilenleri uygula** → **Dilimle**.
4. Beğenmediyseniz **Geri al**; beğendiyseniz profili Orca'da kaydedin.

Eklentinin kayıtları Orca'nın veri klasöründeki `orca_plugins` altında durur;
Orca günlükleri `%APPDATA%\OrcaSlicer\log` klasöründedir.

---

**English quick notes:** the program needs Windows 10/11 with Edge WebView2 and one of Bambu
Studio / QIDI Studio / OrcaSlicer installed (printer list and profiles come from there). Data,
settings and logs: `%APPDATA%\3DsetuPia`. If SmartScreen warns, choose *More info › Run anyway*.
The OrcaSlicer plugin (`ayarci.py`) needs OrcaSlicer 2.5.0-beta+: File › Plugins › (arrow next to
Browse plugins) › Install local plugin, tick Activate, then Run.
