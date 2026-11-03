# Geliştirici rehberi / Developer guide

## Dizin yapısı

```
src/ayarci/
  catalog.py    yazılabilir ayarların beyaz listesi (anahtar, sekme, tip, sınırlar, etiketler)
  geometry.py   model ölçümü (numpy): sarkma, temas, ince duvar (ışın), şekil etiketleri
  rules.py      yerel kural motoru (AI'sız mod + AI'a başlangıç önerisi)
  safety.py     güvenlik süzgeci: beyaz liste, tip/sınır, Orca serileştirmesi, tutarlılık
  prompt.py     AI'a giden tek istek + JSON şema + cevap ayrıştırma
  providers.py  AI sağlayıcıları: Anthropic (resmi SDK) + OpenAI uyumlu (urllib)
  i18n.py       Python tarafı mesajları (TR/EN)
  ui.html       panel (HTML/CSS/JS, Orca tema değişkenleriyle)
  ui.py         ui.html'i yükler (paketleyici gömer)
  assist.py     ortak parçalar: ayar deposu, ölç → kurallar → AI → süzgeç hattı
  plugin.py     Orca bağlantısı: panel, anlık görüntüler, iş kuyruğu, uygula/geri al
  --- masaüstü programı (3DsetuPia.exe) ---
  threemf.py    3MF okuma/yazma: ayarlar, nesneler, plakalar, mesh'ler; yazarken yalnızca
                değişen girdiler değişir (mesh, boyama, renkler bayt bayt kopyalanır)
  projcfg.py    project_settings.config değerleri: filament yuvası, nozul/varyant dizileri,
                different_settings_to_system
  profiles.py   kurulu slicer'ların profil kütüphanesi (system/<Vendor>.json, inherits, "nil",
                compatible_printers[_condition]), diskte önbellek, hedef yazıcı için tam ayar kurma
  placement.py  plaka ızgarası, yeni tablada ortalama / yeniden dizme / sığmıyor raporu
  meshfiles.py  STL/OBJ okuma, ayarsız 3MF'ten mesh, sıfırdan Bambu biçiminde 3MF kurma
  engine.py     programın iş akışı (aç → hazırla → kaydet), pencereden bağımsız
  app.py        pywebview penceresi + köprü; --selftest / --uitest modları
  app.html      programın arayüzü (TR/EN, açık/koyu)
  ayarci.ico    simge (tools/make_icon.py üretir)
src/ayarci_desktop.py  programın giriş noktası
tools/
  build_plugin.py  src → dist/ayarci.py (Orca'nın kurduğu tek dosya)
  build_exe.py     src → dist/3DsetuPia.exe (PyInstaller, tek dosya) + SHA256SUMS.txt
  make_icon.py     simgeyi çizer (numpy, kütüphanesiz)
  set_owner.py     GitHub kullanıcı adı / yazar yer tutucularını doldurur
  preview_ui.py/.js  eklenti panelini Orca olmadan tarayıcıda çizer
tests/            pytest; fake_orca.py gerçek Orca API yüzeyini taklit eder,
                  profilelib.py diskte küçük bir slicer profil kütüphanesi kurar
```

## Masaüstü programı nasıl çalışır

- **Aynı yazıcı:** `project_settings.config` kopyalanır, yalnızca onaylanan anahtarlar yazılır.
  Liste değerlerinde yalnızca seçilen filamentin girdileri değişir; aynı ayarın diğer nozul/varyant
  girdileri, etkin girdideki değişimle orantılı kaydırılır (sıcaklıkta fark, diğerlerinde oran).
- **Başka yazıcı:** `profiles.Library.build_config()` makine + işlem + filament profillerini
  miras zinciriyle çözer, filament başına tek değere indirir (tek nozullu hedef), hedef profilde
  olmayan filament başına anahtarları kaynak projeden tamamlar. Sonra `placement.relocate()`
  build item dönüşümlerini taşır ve `Application` adı hedef slicer'a çevrilir.
  Çok nozullu hedefler bilinçli olarak reddedilir (`multi_nozzle_target`).
- **Değerlerin doğruluğu** gerçek slicer'larla doğrulandı: Bambu Studio, QIDI Studio ve
  OrcaSlicer'ın komut satırı dilimleyicisi (`<exe> --slice 0 --outputdir <klasör> <dosya.3mf>`)
  çıktıyı dilimler ve `result.json` + G-code başlığındaki `; anahtar = değer` satırları
  okunur. Değişiklik yaparken bu kontrolü tekrar etmek önemli; örnek bulgular:
  - Birden çok filamentli projede `filament_shrink` gibi filament başına bir anahtar eksik
    kalırsa QIDI Studio 2.7 "Failed slicing the model" verir.
  - Bambu/Orca'da "Rectilinear" deseni `zig-zag` olarak saklanır; organik destek Orca'da
    `organic`, Bambu/QIDI'de `tree_organic`. `catalog.py` bu farkları `extra` alanıyla tutar.

Programı kaynaktan çalıştırmak:

```bash
python src/ayarci_desktop.py
```

Pencereyi otomatik sürüp sonucu JSON'a yazmak (ekran erişimi gerekmez):

```bash
python src/ayarci_desktop.py --uitest "C:\yol\proje.3mf" "%TEMP%\ui.json" "qidi|Q2 0.4 nozzle"
```

## Mimari ve iş parçacıkları (OrcaSlicer eklentisi)

OrcaSlicer 2.5.0-beta ve sonrasında *Script* eklentisinin `execute()` metodu arka plandaki bir
**Script worker** iş parçacığında çalışır (Orca kaynak: `docs/HLSD/python-plugin-async-bridge.md`).

- `execute()` paneli açar ve bir komut kuyruğunu dinler. Ağır işler (ölçüm, AI isteği) ve
  **ayar yazma** (`orca.host.preset.*.begin_update()/set()/commit()`) burada yapılır.
  `begin_update` sadece bu worker'dan çağrılabilir.
- `on_message()` (panelden gelen mesajlar) **UI iş parçacığında** çalışır: canlı nesneleri
  (model, profiller) yalnızca burada okuyup düz kopyalara çevirir ve kuyruğa atar; asla ağ beklemez.
- 2.5.0-alpha'da Script UI iş parçacığında çalışıyordu ve ayar yazma API'si yoktu; `execute()`
  bu durumda hemen hata döner (aksi halde Orca donardı).

### İzinler

Orca eklentileri bir denetim kancasıyla izler. Worker'dan yapılan ilk ağ bağlantısında Orca bir
izin penceresi gösterir ve **o denemeyi reddeder**; kullanıcı "Evet" derse izin kalıcı olur ve
sonraki deneme geçer. Bu yüzden arayüz "izin verin, tekrar deneyin" der. Sertifika dosyası ve
Anthropic SDK eklenti yüklenirken içe aktarılır (yükleme sırasında izin penceresi eşzamanlı çalışır).

### Ayar değerleri

Orca ayarları metin olarak saklar: sayılar `"0.2"`, yüzdeler `"15%"`, mantıksal `"1"/"0"`,
seçenekler iç anahtarıyla (`"tree(auto)"`), vektörler virgülle (`"200,200"`).
`safety.serialize()` mevcut değerin biçimini korur (vektör uzunluğu dahil).

## Geliştirme ortamı

```bash
python -m pip install -r requirements-dev.txt -r requirements-app.txt
```

```bash
python -m pytest -q
```

```bash
python tools/build_plugin.py
```

```bash
python tools/build_exe.py
```

Paneli Orca olmadan görmek (Node + Playwright gerekir):

```bash
python tools/preview_ui.py docs/img
```

```bash
node tools/preview_ui.js docs/img
```

## Nasıl yapılır

**Yeni bir ayar eklemek:** `catalog.py` → `SETTINGS` içine anahtar (Orca'nın `PrintConfig.cpp`
adıyla birebir), sekme, tip, güvenli `min`/`max`, TR/EN etiket. Gerekirse `safety._limits()`
içine dinamik sınır. AI istemine otomatik girer. Test ekle.

**Yeni bir kural:** `rules.propose()` içinde `out.add(key, value, tr, en)`. Kurallar yalnızca
anlamlı fark varsa öneri üretmeli; güvenlik süzgeci aynı değeri zaten eler.

**Yeni bir AI sağlayıcısı:** OpenAI uyumluysa `providers.PROVIDERS` içine bir kayıt yeterli
(`base_url`, `needs_key`, `url_editable`, `key_page`, `help`) ve `PROVIDER_ORDER`'a ekle.

**Arayüz metni:** `ui.html` içindeki `T.tr` / `T.en`; Python mesajları `i18n.py`.

## Sürüm çıkarma kontrol listesi

1. `app.py` → `APP_VERSION`, `plugin.py` → `PLUGIN_VERSION`
2. `CHANGELOG.md`
3. `python tools/build_plugin.py`, `python -m pytest -q`, `python tools/build_exe.py`
4. Gerçek yazıcılarda duman testi (docs/YAYINLAMA.md §4)
5. GitHub Release + `dist/3DsetuPia.exe`, `dist/ayarci.py`, `dist/SHA256SUMS.txt`

## Bilinçli tasarım kararları

- **AI sayıları serbestçe seçemez**: beyaz liste + sınırlar + mevcut profile göre göreli hız sınırı (%30).
- **Model dosyası gönderilmez**: yalnızca ölçümler. Gizlilik ve maliyet için.
- **Kaydetmez**: değişiklikler Orca'da "kaydedilmemiş" kalır; kullanıcı kontrolü elinde tutar.
- **Tek istek**: AI'a tek bir toplu soru gider (hızlı, ucuz, öngörülebilir).
- **AI hatasında kurallara döner**: kullanıcı asla eli boş kalmaz, uyarıyla bilgilendirilir.
- **Nesne bazlı ayarlar ve boyamaya dokunulmaz**, uyarı verilir.
