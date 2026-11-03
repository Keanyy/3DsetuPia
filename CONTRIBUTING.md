# Katkıda bulunma / Contributing

3DsetuPia'ya katkı verdiğin için teşekkürler! / Thanks for helping!

## Hata bildirimi / Bug reports

[Issues](https://github.com/Keanyy/3DsetuPia/issues) → "Hata bildirimi" şablonu. Lütfen ekle:
3DsetuPia sürümü (program mı, Orca eklentisi mi), slicer ve sürümü, yazıcı/filament, ne beklediğin /
ne oldu, ve mümkünse `ayarci_last_run.json` ile 3MF dosyası (program: `%APPDATA%\3DsetuPia`;
API anahtarı içermez).

Please include your 3DsetuPia version (program or Orca plugin), slicer and version, printer/filament,
expected vs. actual behaviour, and if possible `ayarci_last_run.json` and the 3MF (contains no API key).

## Kod / Code

1. Fork → branch → değişiklik / change.
2. `py -m pytest -q` yeşil olmalı / must pass.
3. Kaynakları düzenle (`src/ayarci/`), `dist/ayarci.py` dosyasını elle düzenleme; `python tools/build_plugin.py` üretir.
   Edit sources, never `dist/ayarci.py` by hand.
4. Yeni ayar/kural/sağlayıcı için test ekle. Add tests for new settings, rules or providers.
5. Arayüz metinleri hem Türkçe hem İngilizce olmalı. UI strings need both TR and EN.

Rehber: [docs/GELISTIRME.md](docs/GELISTIRME.md)

## Kurallar / Ground rules

- Güvenlik süzgeci gevşetilmez: renk, boyama, G-code, makine ayarları kapsam dışıdır.
  The safety filter stays strict: colours, painting, G-code and machine settings are out of scope.
- Kullanıcının modeli bilgisayardan çıkmaz. The user's model never leaves their PC.
- Saygılı ve yapıcı iletişim. Be kind and constructive.

Katkılar AGPL-3.0 lisansı altında kabul edilir. Contributions are accepted under AGPL-3.0.
