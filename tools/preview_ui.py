#!/usr/bin/env python3
"""Build mocked panel data for tools/preview_ui.js (renders the panel without OrcaSlicer).

Usage: python tools/preview_ui.py [outdir] && node tools/preview_ui.js [outdir]
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))


import meshes as M  # noqa: E402
from fixtures import ctx  # noqa: E402
from ayarci import geometry, rules, safety, providers  # noqa: E402
from ayarci.catalog import PAGES, PAGE_ORDER  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "img")


def payloads(lang):
    c = ctx(intent="looks", lang=lang)
    mesh = M.merge(M.cylinder(3, 30), M.cylinder(25, 5, oz=30))
    an = geometry.analyze_plate([M.part("mantar_lamba", mesh)])
    ch, _ = safety.validate(rules.propose(an, c), c)
    init = {"command": "init", "version": "1.0.0", "orca_version": "2.5.0", "lang": lang,
            "providers": providers.public_meta(lang),
            "settings": {"provider": "anthropic", "providers": {"anthropic": {"has_key": True, "key_hint": "…9xQe",
                                                                              "model": "claude-opus-5-5", "tested": True}}},
            "caps": {"can_write": True}, "pages": {k: v[lang] for k, v in PAGES.items()}, "page_order": PAGE_ORDER,
            "storage": "C:\\Users\\you\\AppData\\Roaming\\OrcaSlicer\\orca_plugins\\data\\ayarci",
            "repo": "https://github.com/Keanyy/3DsetuPia",
            "objects": [{"name": "mantar_lamba", "instances": 1, "size_mm": an["objects"][0]["size_mm"]}],
            "process_name": "0.20mm Standard @BBL P1S", "printer_name": "Bambu Lab P1S 0.4 nozzle", "nozzle": "0.4",
            "bed_type": "Textured PEI Plate", "filament_slot1": "Bambu PLA Basic @BBL P1S",
            "filament_selected": "Bambu PLA Basic @BBL P1S", "filament_slots": 1,
            "filament_choices": [{"name": "Bambu PLA Basic @BBL P1S"}, {"name": "Elegoo PETG @base"},
                                 {"name": "Polymaker PLA Pro"}]}
    summary = ("Mantar biçimli lamba: ince bir gövde üzerinde geniş bir şapka var. Şapkanın altı desteksiz "
               "basılamaz ve gövde tabana çok az değiyor; görünüş için ince katman, ütüleme ve brim seçtim.") \
        if lang == "tr" else ("Mushroom-shaped lamp: a wide cap on a thin stem. The cap underside needs support and the "
                              "stem barely touches the bed; for looks I chose thin layers, ironing and a brim.")
    prop = {"command": "proposals", "ok": True, "source": "ai", "summary": summary, "changes": ch,
            "warnings": [], "analysis": an, "seconds": 18.4, "filament_switch": False}
    return init, prop


def main():
    """Write the mocked bridge payloads; tools/preview_ui.js renders them with Playwright."""
    os.makedirs(OUT, exist_ok=True)
    data = {lang: dict(zip(("init", "prop"), payloads(lang))) for lang in ("tr", "en")}
    path = os.path.join(OUT, "_preview_payloads.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
