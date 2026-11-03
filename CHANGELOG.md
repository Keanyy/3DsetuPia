# Değişiklikler / Changelog

## 1.1.0 – 3DsetuPia programı / the 3DsetuPia program

Proje artık **3DsetuPia** adını taşıyor ve slicer'dan bağımsız bir Windows programı olarak geliyor.

- **3DsetuPia.exe**: 3MF projesi, ayarsız 3MF, STL veya OBJ açar; modeli ölçer, ayarları önerir ve
  seçilenleri **yeni bir 3MF** dosyasına yazar. Kaynak dosya hiç değişmez.
- Bambu Studio, QIDI Studio ve OrcaSlicer projeleri (aynı 3MF biçimini kullanan diğer slicer'lar dahil).
- Yazıcı, nozul, tabla ve filamentler dosyadan okunur. Çift nozullu yazıcılarda (Bambu H2C/H2D)
  modelin bastığı nozul ve filament esas alınır; diğer nozul/varyant değerleri orantılı korunur.
- **Başka yazıcıya taşıma**: bilgisayardaki slicer'ların üreticiden gelen profilleri (makine, işlem,
  filament) kullanılır; filamentler en yakın profille eşleşir; nesneler yeni tablanın ortasına
  taşınır, sığmazsa yeniden dizilir, sığmayan nesne bildirilir. Renkler ve boyama korunur.
- Dilimlenmiş `.gcode.3mf` dosyaları dilimlenmemiş proje olarak kaydedilir.
- Çıktılar Bambu Studio 2.8, QIDI Studio 2.7 ve OrcaSlicer 2.4'ün kendi komut satırı
  dilimleyicisiyle test edildi.
- Seçenek değerleri slicer'a göre süzülür (ör. Orca'nın `organic` desteği Bambu/QIDI'de
  `tree_organic`); "Rectilinear" desenin gerçek adı `zig-zag` olarak düzeltildi.
- Arayüz: sürükle-bırak, slicer'da aç, klasörü göster, açık/koyu tema, TR/EN.
- Gizli test modları: `--selftest <dosya> <klasör> [hedef]` ve `--uitest`.

The project is now called **3DsetuPia** and ships as a standalone Windows program that writes a new,
improved 3MF for Bambu Studio, QIDI Studio and OrcaSlicer projects, can move a project to another
printer using the installed slicers' vendor profiles, and re-centres objects on the new bed.
The OrcaSlicer plugin (`ayarci.py`) shares the same core.

## 1.0.0 – ilk sürüm / first release

- OrcaSlicer 2.5 eklentisi: tabladaki modeli ölçer (sarkma, tabana temas, duvar kalınlığı, devrilme riski, şekil).
- Kalite, Dayanıklılık, Hız, Destek, Diğer ve Filament sekmelerinde modele özel ayar önerileri, nedenleriyle.
- Onaylı uygulama ve tek tıkla geri alma; değişiklikler kaydedilmeden bekler.
- Filament seçimi (1. yuva) ve öncelik: Dengeli / Görünüş / Dayanıklılık / Hız.
- Yapay zekâ sağlayıcıları: Anthropic Claude, OpenAI, Google Gemini, OpenRouter, DeepSeek, Groq, Mistral,
  Ollama, LM Studio, özel OpenAI uyumlu adres; ya da yapay zekâsız yerel kurallar.
- Güvenlik süzgeci: beyaz liste, güvenli aralıklar, renk/boyama/G-code/makine ayarlarına erişim yok.
- Türkçe ve İngilizce arayüz, açık/koyu tema.

Requires OrcaSlicer 2.5.0-beta or newer.
