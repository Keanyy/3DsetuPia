"""3DsetuPia - messages shown by the Python side (the page has its own strings)."""

MESSAGES = {
    "tr": {
        "test_none": "Yerel kurallar modu seçili. İnternet ya da anahtar gerekmez.",
        "test_ok": "Bağlantı başarılı. {n} model bulundu; listeden birini seçip Kaydet'e basın.",
        "err_permission": "Orca bu eklentinin {host} adresine bağlanması için izin istiyor. Açılan izin "
                          "penceresinde 'Evet' deyin, ardından aynı düğmeye tekrar basın.",
        "err_auth": "API anahtarı kabul edilmedi. Anahtarı kontrol edip yeniden kaydedin.",
        "err_network": "{host} adresine ulaşılamadı. İnternet bağlantınızı (yerel AI için programın "
                       "açık olduğunu) kontrol edin. Ayrıntı: {detail}",
        "err_model": "Seçilen model bulunamadı. 'Bağlantıyı test et' ile listeyi yenileyip başka bir "
                     "model seçin. ({detail})",
        "err_missing_key": "Bu sağlayıcı için API anahtarı gerekli.",
        "err_missing_url": "Bağlantı adresi gerekli.",
        "err_bad_url": "Adres http:// ya da https:// ile başlamalı.",
        "err_missing_model": "Önce bir model seçin ('Bağlantıyı test et' listeyi getirir).",
        "err_refusal": "AI bu isteği yanıtlamadı.",
        "err_generic": "AI hatası: {detail}",
        "err_parse": "AI cevabı okunamadı ({detail}).",
        "fallback_rules": "Bu sefer yerel kurallar kullanıldı.",
        "no_model": "Tablada basılabilir bir model yok. Önce bir model ekleyin.",
        "measuring": "Model ölçülüyor…",
        "asking_ai": "{name} ayarları hazırlıyor… (yarım dakika kadar sürebilir)",
        "rules_summary": "Ayarlar yerleşik kurallarla, modelin ölçümlerine göre hazırlandı.",
        "rejected": "AI'ın {n} önerisi güvenlik süzgecinden geçemediği için atlandı.",
        "object_overrides": "Şu nesnelerin kendine özel ayarları var, onlar değişmez: {names}.",
        "multi_filament": "Birden fazla filament var. 3DsetuPia yalnızca 1. filamenti ayarlar; renk ve "
                          "boyama ayarlarına dokunmaz.",
        "painted": "Modelde renk boyaması var. 3DsetuPia boyamaya ve renk atamalarına dokunmaz.",
        "no_write_api": "Bu Orca sürümü eklentilerin ayar yazmasına izin vermiyor. Önerileri elle "
                        "uygulayabilir ya da Orca'yı 2.5 veya daha yeni bir sürüme güncelleyebilirsiniz.",
        "nothing": "Önce 'Ayarları hazırla' ile öneri oluşturun.",
        "nothing_selected": "Uygulanacak öneri seçilmedi.",
        "apply_failed": "Uygulanamadı, hiçbir ayar değişmedi: {detail}",
        "apply_partial": "Uygulama yarıda kaldı: {n} ayar uygulandı, gerisi uygulanamadı ({detail}). "
                         "'Geri al' ile uygulananları geri alabilirsiniz.",
        "applied": "{n} ayar uygulandı. Ayarlar henüz kaydedilmedi: beğenirseniz Orca'da profili "
                   "kaydedin. Şimdi 'Dilimle'ye basabilirsiniz.",
        "nothing_to_undo": "Geri alınacak bir değişiklik yok.",
        "stale": "Öneriler hazırlandıktan sonra Orca'da profil ya da filament değişti. Güvenli olması "
                 "için 'Ayarları hazırla'ya tekrar basın.",
        "undo_failed": "Geri alınamadı: {detail}",
        "undone": "Değişiklikler geri alındı.",
        # ---- desktop program
        "loading_profiles": "Bilgisayardaki yazıcı profilleri okunuyor… (ilk açılışta biraz sürebilir)",
        "open_failed": "Dosya açılamadı: {detail}",
        "unsupported": "Bu dosya türü desteklenmiyor. 3MF, STL veya OBJ dosyası seçin.",
        "bad_mesh": "Model dosyası okunamadı ({detail}).",
        "bad_settings": "Projedeki ayar dosyası bozuk ({detail}).",
        "no_settings": "Bu dosyada slicer ayarı yok (yalnızca model). Hedef yazıcıyı seçin; ayarlar "
                       "o yazıcının kendi profillerinden kurulur.",
        "need_target": "Önce hedef yazıcıyı seçin.",
        "multi_nozzle_target": "{name} çok nozullu bir yazıcı. Başka bir yazıcının projesini buna dönüştürmeyi "
                               "şimdilik slicer'ın kendisi yapmalı: dosyayı Bambu Studio'da açıp yazıcıyı "
                               "seçin, projeyi kaydedin ve o dosyayı 3DsetuPia'ya verin.",
        "profile_missing": "Hedef yazıcı için profil bulunamadı: {detail}",
        "sliced_input": "Dosya dilimlenmiş (G-code içeriyor). Yeni dosya dilimlenmemiş proje olarak "
                        "kaydedilir; slicer'da tekrar 'Dilimle'ye basın.",
        "retarget": "Proje {src} yerine {dst} için kuruldu. Yazıcı, işlem ({process}) ve filament profilleri "
                    "üreticinin kendi profillerinden alındı; renkler ve boyama korunur.",
        "fil_mapped": "Filament {slot}: {src} → {dst}",
        "place_moved": "Plaka {plate}: nesneler yeni tablanın ortasına taşındı, dizilişleri korundu.",
        "place_packed": "Plaka {plate}: nesneler yeni tablaya sığacak şekilde yeniden dizildi.",
        "place_crowded": "Plaka {plate}: nesneler tek tek sığıyor ama hepsi birden sığmıyor. Slicer'da "
                         "'Yerleştir' (A tuşu) ile dizin ya da bazılarını yeni plakaya taşıyın.",
        "place_too_big": "Plaka {plate}: şu nesneler bu tablaya sığmıyor: {names}. Küçültmek ya da bölmek gerekir.",
        "place_too_tall": "Şu nesneler bu yazıcının basabileceği yükseklikten uzun: {names}.",
        "place_new": "Model tablanın ortasına yerleştirildi.",
        "place_new_too_big": "Model bu yazıcının tablasına sığmıyor.",
        "saved_to": "Kaydedildi: {path}",
        "save_failed": "Kaydedilemedi: {detail}",
        "multi_filament_app": "Projede {n} filament var. Ayarlanan: {name} (modelde en çok kullanılan). "
                              "Diğer filamentlere, renklere ve boyamaya dokunulmaz.",
        "slicer_missing": "Bu slicer bilgisayarda bulunamadı; dosyayı kendiniz açın.",
        "same_printer": "Dosyadaki yazıcı ({name})",
        "same_file": "kaynak dosyanın üzerine yazılamaz, başka bir ad seçin",
    },
    "en": {
        "test_none": "Local rules mode is selected. No internet or key needed.",
        "test_ok": "Connected. {n} models found; pick one and press Save.",
        "err_permission": "OrcaSlicer asks permission for this plugin to connect to {host}. Click "
                          "'Yes' in the permission dialog, then press the same button again.",
        "err_auth": "The API key was rejected. Check it and save it again.",
        "err_network": "Could not reach {host}. Check your internet connection (or that the local AI "
                       "app is running). Detail: {detail}",
        "err_model": "The selected model was not found. Refresh the list with 'Test connection' and "
                     "pick another one. ({detail})",
        "err_missing_key": "This provider needs an API key.",
        "err_missing_url": "A server address is required.",
        "err_bad_url": "The address must start with http:// or https://.",
        "err_missing_model": "Pick a model first ('Test connection' loads the list).",
        "err_refusal": "The AI declined to answer this request.",
        "err_generic": "AI error: {detail}",
        "err_parse": "Could not read the AI answer ({detail}).",
        "fallback_rules": "Local rules were used this time.",
        "no_model": "There is no printable model on the plate. Add a model first.",
        "measuring": "Measuring the model…",
        "asking_ai": "{name} is preparing settings… (may take about half a minute)",
        "rules_summary": "Settings were prepared by the built-in rules from the model measurements.",
        "rejected": "{n} AI suggestion(s) failed the safety filter and were skipped.",
        "object_overrides": "These objects have their own per-object settings, which stay as they are: {names}.",
        "multi_filament": "Several filaments are used. 3DsetuPia only tunes filament 1 and never touches "
                          "colours or painting.",
        "painted": "The model is colour-painted. 3DsetuPia never touches painting or colour assignments.",
        "no_write_api": "This OrcaSlicer version does not let plugins write settings. Apply the "
                        "suggestions by hand, or update OrcaSlicer to 2.5 or newer.",
        "nothing": "Create suggestions first with 'Prepare settings'.",
        "nothing_selected": "No suggestion selected.",
        "apply_failed": "Could not apply; no setting was changed: {detail}",
        "apply_partial": "Applying stopped halfway: {n} setting(s) applied, the rest failed ({detail}). "
                         "Use 'Undo' to revert the applied ones.",
        "applied": "{n} setting(s) applied. They are not saved yet: save the profile in OrcaSlicer "
                   "if you like them. You can press 'Slice' now.",
        "nothing_to_undo": "Nothing to undo.",
        "stale": "The profile or filament changed in OrcaSlicer after the suggestions were made. "
                 "Press 'Prepare settings' again to be safe.",
        "undo_failed": "Could not undo: {detail}",
        "undone": "Changes were undone.",
        # ---- desktop program
        "loading_profiles": "Reading the printer profiles on this PC… (may take a moment the first time)",
        "open_failed": "Could not open the file: {detail}",
        "unsupported": "This file type is not supported. Choose a 3MF, STL or OBJ file.",
        "bad_mesh": "Could not read the model file ({detail}).",
        "bad_settings": "The project's settings file is damaged ({detail}).",
        "no_settings": "This file has no slicer settings (model only). Choose the target printer; settings "
                       "are set up from that printer's own profiles.",
        "need_target": "Choose the target printer first.",
        "multi_nozzle_target": "{name} is a multi-nozzle printer. Converting another printer's project to it is "
                               "best done by the slicer itself for now: open the file in Bambu Studio, pick "
                               "the printer, save the project and give that file to 3DsetuPia.",
        "profile_missing": "No profile found for the target printer: {detail}",
        "sliced_input": "The file is sliced (contains G-code). The new file is saved as an unsliced project; "
                        "press 'Slice' again in your slicer.",
        "retarget": "The project was set up for {dst} instead of {src}. Printer, process ({process}) and "
                    "filament profiles come from the manufacturer's own profiles; colours and painting are kept.",
        "fil_mapped": "Filament {slot}: {src} → {dst}",
        "place_moved": "Plate {plate}: objects moved to the centre of the new bed, arrangement kept.",
        "place_packed": "Plate {plate}: objects re-arranged to fit the new bed.",
        "place_crowded": "Plate {plate}: each object fits but not all together. Use 'Arrange' (A key) in "
                         "your slicer or move some to a new plate.",
        "place_too_big": "Plate {plate}: these objects do not fit this bed: {names}. They need scaling or cutting.",
        "place_too_tall": "These objects are taller than this printer can print: {names}.",
        "place_new": "The model was placed in the centre of the bed.",
        "place_new_too_big": "The model does not fit this printer's bed.",
        "saved_to": "Saved: {path}",
        "save_failed": "Could not save: {detail}",
        "multi_filament_app": "The project uses {n} filaments. Tuned: {name} (used most by the model). Other "
                              "filaments, colours and painting are left alone.",
        "slicer_missing": "This slicer was not found on this PC; open the file yourself.",
        "same_printer": "Printer in the file ({name})",
        "same_file": "the source file cannot be overwritten, choose another name",
    },
}


def msg(lang, key, **kw):
    table = MESSAGES.get(lang) or MESSAGES["en"]
    text = table.get(key) or MESSAGES["en"].get(key) or key
    try:
        return text.format(**kw)
    except (KeyError, IndexError):
        return text
