# Yayınlama ve topluluğa duyurma rehberi (Windows 11)

Bu rehber programı derlemeyi, test etmeyi, GitHub'a koymayı, ilk sürümü yayınlamayı ve
duyurmayı adım adım anlatır. Sıra önemlidir: **önce kendi yazıcılarında test et, sonra yayınla.**

---

## 0. Hazırlık (bir kez)

1. **GitHub hesabı** (var ✓). Kullanıcı adını not et; aşağıda `KULLANICI` diye geçiyor.
2. **GitHub Desktop**: <https://desktop.github.com> → GitHub hesabınla giriş yap.
3. **Python 3.14** kurulu ✓. Komutlarda `python` yerine **`py`** yaz (bu bilgisayarda `python`
   komutu Microsoft Store kısayoluna gidiyor).
4. Derleme ortamı (bir kez; OneDrive dışında durur):

```bash
py -3.14 -m venv %LOCALAPPDATA%\3DsetuPia-venv
```

```bash
%LOCALAPPDATA%\3DsetuPia-venv\Scripts\python -m pip install -r requirements-app.txt -r requirements-dev.txt
```

Aşağıdaki komutlarda `PY` = `%LOCALAPPDATA%\3DsetuPia-venv\Scripts\python`.

> İpucu: OneDrive klasörleri bazen git ile sorun çıkarır (eşitleme kilitleri). Sorun yaşarsan
> projeyi `C:\Projeler\3DsetuPia` gibi OneDrive dışı bir yere taşı.

## 1. Ad ve depo adresi (yapıldı)

Proje `Keanyy` / Kenan ÇELİK adına ayarlandı (`tools/owner.txt`). Başka bir ad kullanmak istersen:

```bash
PY tools/set_owner.py --github KULLANICI --author "Ad Soyad"
```

## 2. Testleri çalıştır

```bash
PY -m pytest -q
```

Hepsi "passed" olmalı (şu an 63 test).

## 3. Programı derle

```bash
PY tools/build_exe.py
```

Sonuç: `dist\3DsetuPia.exe` (yaklaşık 34 MB) ve `dist\SHA256SUMS.txt`.

Hızlı kendi kendine test (pencere açmadan; sonuç `selftest.json` dosyasına yazılır):

```bash
dist\3DsetuPia.exe --selftest "C:\yol\dosya.3mf" "%TEMP%\3dsetupia-test"
```

## 4. Gerçek yazıcılarda dene (en önemli adım)

Ofiste **Bambu H2C**, evde **QIDI Q2** ile:

- [ ] `3DsetuPia.exe` açılıyor; SmartScreen uyarısında "Yine de çalıştır" ile geçiliyor.
- [ ] Yazıcı listesinde kurulu yazıcıların (H2C / Q2) görünüyor.
- [ ] Kendi kaydettiğin bir proje 3MF'i: yazıcı, işlem profili, filamentler doğru görünüyor.
- [ ] "Ayarları hazırla" → öneriler mantıklı; "Yeni 3MF olarak kaydet" → "… ile aç" slicer'da açıyor.
- [ ] Slicer'da ayarlar değişmiş görünüyor (profil adının yanında "değiştirildi" işareti),
      renkler/boyama yerinde, **Dilimle** sorunsuz.
- [ ] Başka yazıcı için hazırlanmış bir 3MF'i (ör. MakerWorld) kendi yazıcına taşı: nesneler
      tablanın ortasında, filamentler makul eşleşmiş.
- [ ] STL aç → yazıcı seç → kaydet → slicer'da açılıyor ve dilimleniyor.
- [ ] AI Ayarı: bir sağlayıcı bağlanıyor; anahtar yanlışsa anlaşılır hata veriyor.
- [ ] Küçük bir test baskısı başarılı.

Bir sorun çıkarsa: Claude oturumunda proje klasörünü aç, "CLAUDE.md'yi oku, şu hatayı düzelt"
de ve `%APPDATA%\3DsetuPia` içindeki `ayarci_last_run.json` / `ayarci_error.log` dosyalarını ekle.

## 5. GitHub'a yükle

1. GitHub Desktop → **File › Add local repository** → proje klasörünü seç.
2. "Bu klasör bir depo değil" derse **create a repository**:
   - Name: `3DsetuPia`
   - Git ignore / License: **None** (proje kendi dosyalarını içeriyor)
3. Sol altta özet: `İlk sürüm 1.1.0` → **Commit to main**.
4. **Publish repository** → "Keep this code private" işaretini **kaldır** → Publish.
5. Depo sayfasında ⚙ (About): açıklama *AI print-settings assistant for Bambu Studio, QIDI Studio
   and OrcaSlicer 3MF projects*; konular: `3d-printing`, `bambu-studio`, `qidi`, `orcaslicer`,
   `slicer`, `3mf`, `ai`.

`3DsetuPia.exe` depoya girmez (`.gitignore`); Release'e eklenir.

## 6. İlk sürümü (Release) yayınla

1. Depo sayfası → **Releases** → **Draft a new release**.
2. **Choose a tag** → `v1.1.0` → *Create new tag*.
3. Başlık: `3DsetuPia 1.1.0`. Açıklamaya `CHANGELOG.md`'deki 1.1.0 bölümünü yapıştır; altına
   `SHA256SUMS.txt` içeriğini ekle.
4. **Attach binaries**: `dist\3DsetuPia.exe`, `dist\ayarci.py`, `dist\SHA256SUMS.txt`.
5. **Publish release**.

Yayından önce `3DsetuPia.exe`'yi <https://www.virustotal.com> adresinde taratıp bağlantısını
sürüm notuna eklemek güven verir. (İmzasız tek dosyalık programlarda bir iki antivirüs yanlış
alarm verebilir; bu normaldir.)

> **Kod imzası (ileride):** SmartScreen uyarısını kaldırmak için kod imzası gerekir. Açık kaynak
> projelere ücretsiz imza veren programlar var (ör. SignPath Foundation). Proje biraz büyüyünce
> başvurmaya değer.

## 7. (İsteğe bağlı) OrcaSlicer eklentisini Orca Cloud'a yayınla

OrcaSlicer 2.5 kullananlar için `dist/ayarci.py` eklentisi Orca Cloud'a da konabilir:
orcaslicer.com → Orca Cloud → Plugins → yazar/yayınla adımları. Bu adımlar yeni ve buradan
doğrulanamadı; Claude oturumunda "Orca Cloud'a eklenti nasıl yayınlanır, siteden bakıp anlat" de.

## 8. Topluluğa duyur

Kısa, dürüst ve görselli bir duyuru en iyisidir. Hazır metin (İngilizce):

> **3DsetuPia – free, open-source assistant that tunes your Bambu Studio / QIDI Studio / OrcaSlicer
> project for the model in it**
> Drop a 3MF (or STL) on it: it measures the model locally (overhangs, bed contact, wall thickness,
> tipping risk), reads your printer and filaments, and proposes changes across
> Quality/Strength/Speed/Support/Filament, with reasons. You pick, it writes a new 3MF. It can also
> move a project to another printer using that printer's own profiles and re-centre it on the bed.
> Works offline with built-in rules, or with Claude, OpenAI, Gemini, local Ollama…
> Never touches colours, painting or G-code; your model never leaves your PC.
> AGPL-3.0: https://github.com/KULLANICI/3DsetuPia — feedback very welcome!

Türkçe kısa metin:

> **3DsetuPia** – Bambu Studio, QIDI Studio ve OrcaSlicer projelerini modele göre ayarlayan ücretsiz,
> açık kaynak program. 3MF'i sürükle bırak; modeli ölçer, yazıcını ve filamentini okur, Kalite /
> Dayanıklılık / Hız / Destek / Filament ayarlarını nedenleriyle önerir, seçtiklerini yeni bir 3MF'e
> yazar. Başka yazıcı için hazırlanmış dosyayı kendi yazıcına da taşır. Yapay zekâsız da çalışır.
> https://github.com/KULLANICI/3DsetuPia

Nereye:

1. **Reddit**: r/BambuLab, r/QidiTech3D, r/OrcaSlicer, r/3Dprinting (kurallarını okuyup tek gönderi).
2. **OrcaSlicer GitHub Discussions** → *Show and tell*.
3. **Türkiye**: 3D yazıcı Facebook grupları, Technopat ve DonanımHaber forumları, Discord sunucuları.
   Türkçe arayüz burada büyük artı.
4. **Kısa video** (30–60 sn): dosyayı sürükle → Ayarları hazırla → kaydet → slicer'da aç → dilimle.

İlk haftalarda gelen hata bildirimlerine hızlı cevap vermek projeye güven kazandırır.

## 9. Bağış (isteğe bağlı)

- **GitHub Sponsors** Türkiye'de para alabilen ülkeler listesinde: <https://github.com/sponsors> →
  *Get sponsored*. Onaylanınca depo sayfasında **Sponsor** düğmesi çıkar (`.github/FUNDING.yml` hazır).
- Alternatif: Patreon ya da Kreosus; bağlantıyı `.github/FUNDING.yml` dosyasına ekle.

## 10. Yeni sürüm çıkarma (ileride)

1. Kodu değiştir; `src/ayarci/app.py` → `APP_VERSION` ve `src/ayarci/plugin.py` → `PLUGIN_VERSION` artır.
2. `CHANGELOG.md`'ye ekle.
3. `PY tools/build_plugin.py` → `PY -m pytest -q` → `PY tools/build_exe.py`
4. GitHub Desktop → Commit → Push.
5. Yeni Release (`v1.1.1` gibi) + `3DsetuPia.exe`, `ayarci.py`, `SHA256SUMS.txt`.

## 11. Topluluk katkıları

- Gelen **Pull Request**'lerde GitHub otomatik testleri çalıştırır (`.github/workflows/ci.yml`);
  yeşil değilse birleştirme. Aynı iş akışı her değişiklikte `3DsetuPia.exe`'yi de derleyip
  "Artifacts" olarak saklar.
- Yeni ayar/kural önerileri için `docs/GELISTIRME.md` bölümlerini göster.
