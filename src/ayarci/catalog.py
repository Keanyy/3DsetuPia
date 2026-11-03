"""3DsetuPia - the settings the assistant is allowed to change.

Only keys listed here can ever be written. Everything else (colours, painting,
multi-material, G-code, printer/machine settings, post-processing scripts) is
out of reach by design.

Each entry: key -> dict(
    cat   = "process" | "filament",
    page  = UI page id (quality/strength/speed/support/others/filament),
    type  = "int" | "float" | "percent" | "bool" | "enum",
    min / max  (hard limits; dynamic limits are added in safety.py),
    enum  = values every slicer of the family accepts (checked against the Bambu Studio 2.8,
            QIDI Studio 2.7 and OrcaSlicer 2.4 binaries),
    extra = {flavor: [values only that slicer accepts]} ("bambu", "qidi", "orca"),
    unit  = display unit,
    tr / en = human label,
    rel   = optional relative limit for speeds/accelerations ("speed"),
)
"""

PAGES = {
    "quality": {"tr": "Kalite", "en": "Quality"},
    "strength": {"tr": "Dayanıklılık", "en": "Strength"},
    "speed": {"tr": "Hız", "en": "Speed"},
    "support": {"tr": "Destek", "en": "Support"},
    "others": {"tr": "Diğer", "en": "Others"},
    "filament": {"tr": "Filament", "en": "Filament"},
}
PAGE_ORDER = ["quality", "strength", "speed", "support", "others", "filament"]

# "zig-zag" is how all three slicers store the pattern their UI calls "Rectilinear".
_SURFACE_PATTERNS = ["monotonic", "monotonicline", "zig-zag", "alignedrectilinear",
                     "hilbertcurve", "archimedeanchords", "octagramspiral"]
_SURFACE_EXTRA = {"orca": ["concentric"], "qidi": ["concentric"]}
_INFILL_PATTERNS = ["zig-zag", "alignedrectilinear", "zigzag", "crosszag", "lockedzag",
                    "line", "grid", "triangles", "tri-hexagon", "cubic", "adaptivecubic",
                    "supportcubic", "lightning", "honeycomb", "3dhoneycomb", "crosshatch",
                    "gyroid", "hilbertcurve", "archimedeanchords", "octagramspiral"]
_INFILL_EXTRA = {"orca": ["quartercubic", "lateral-honeycomb", "lateral-lattice", "tpmsd", "tpmsfk",
                          "concentric"],
                 "qidi": ["concentric"]}


def _e(cat, page, typ, tr, en, **kw):
    d = {"cat": cat, "page": page, "type": typ, "tr": tr, "en": en}
    d.update(kw)
    return d


SETTINGS = {
    # ---------------- Quality ----------------
    "layer_height": _e("process", "quality", "float", "Katman yüksekliği", "Layer height",
                       min=0.04, max=1.0, unit="mm"),
    "initial_layer_print_height": _e("process", "quality", "float", "İlk katman yüksekliği",
                                     "Initial layer height", min=0.08, max=1.0, unit="mm"),
    "seam_position": _e("process", "quality", "enum", "Dikiş konumu", "Seam position",
                        enum=["nearest", "aligned", "back", "random"], extra={"orca": ["aligned_back"]}),
    "seam_slope_type": _e("process", "quality", "enum", "Eğimli (scarf) dikiş", "Scarf seam",
                          enum=["none", "external", "all"]),
    "wall_generator": _e("process", "quality", "enum", "Duvar üreteci", "Wall generator",
                         enum=["classic", "arachne"]),
    "wall_sequence": _e("process", "quality", "enum", "Duvar sırası", "Wall order",
                        enum=["inner wall/outer wall", "outer wall/inner wall",
                              "inner-outer-inner wall"]),
    "precise_outer_wall": _e("process", "quality", "bool", "Hassas dış duvar", "Precise outer wall"),
    "only_one_wall_top": _e("process", "quality", "bool", "Üst yüzeyde tek duvar",
                            "Only one wall on top surfaces"),
    "detect_overhang_wall": _e("process", "quality", "bool", "Sarkan duvarı algıla",
                               "Detect overhang walls"),
    "thick_bridges": _e("process", "quality", "bool", "Kalın köprüler", "Thick bridges"),
    "ironing_type": _e("process", "quality", "enum", "Ütüleme", "Ironing",
                       enum=["no ironing", "top", "topmost", "solid"]),
    "ironing_pattern": _e("process", "quality", "enum", "Ütüleme deseni", "Ironing pattern",
                          enum=["zig-zag"], extra=_SURFACE_EXTRA),
    "ironing_flow": _e("process", "quality", "percent", "Ütüleme akışı", "Ironing flow",
                       min=3, max=35, unit="%"),
    "ironing_spacing": _e("process", "quality", "float", "Ütüleme aralığı", "Ironing spacing",
                          min=0.05, max=0.3, unit="mm"),
    "ironing_speed": _e("process", "quality", "float", "Ütüleme hızı", "Ironing speed",
                        min=10, max=120, unit="mm/s"),

    # ---------------- Strength ----------------
    "wall_loops": _e("process", "strength", "int", "Duvar sayısı", "Wall loops", min=1, max=10),
    "top_shell_layers": _e("process", "strength", "int", "Üst katman sayısı", "Top shell layers",
                           min=0, max=25),
    "top_shell_thickness": _e("process", "strength", "float", "Üst kabuk kalınlığı",
                              "Top shell thickness", min=0.0, max=3.0, unit="mm"),
    "bottom_shell_layers": _e("process", "strength", "int", "Alt katman sayısı",
                              "Bottom shell layers", min=0, max=25),
    "bottom_shell_thickness": _e("process", "strength", "float", "Alt kabuk kalınlığı",
                                 "Bottom shell thickness", min=0.0, max=3.0, unit="mm"),
    "sparse_infill_density": _e("process", "strength", "percent", "Dolgu yoğunluğu",
                                "Infill density", min=0, max=100, unit="%"),
    "sparse_infill_pattern": _e("process", "strength", "enum", "Dolgu deseni", "Infill pattern",
                                enum=_INFILL_PATTERNS, extra=_INFILL_EXTRA),
    "top_surface_pattern": _e("process", "strength", "enum", "Üst yüzey deseni",
                              "Top surface pattern", enum=_SURFACE_PATTERNS, extra=_SURFACE_EXTRA),
    "bottom_surface_pattern": _e("process", "strength", "enum", "Alt yüzey deseni",
                                 "Bottom surface pattern", enum=_SURFACE_PATTERNS,
                                 extra=_SURFACE_EXTRA),
    "internal_solid_infill_pattern": _e("process", "strength", "enum", "İç katı dolgu deseni",
                                        "Internal solid infill pattern", enum=_SURFACE_PATTERNS,
                                        extra=_SURFACE_EXTRA),
    "ensure_vertical_shell_thickness": _e("process", "strength", "enum",
                                          "Dikey kabuk kalınlığını koru",
                                          "Ensure vertical shell thickness",
                                          enum=[],
                                          extra={"orca": ["none", "ensure_critical_only",
                                                          "ensure_moderate", "ensure_all"],
                                                 "bambu": ["enabled"], "qidi": ["enabled"]}),
    "detect_thin_wall": _e("process", "strength", "bool", "İnce duvarı algıla", "Detect thin walls"),
    "infill_combination": _e("process", "strength", "bool", "Dolgu birleştirme",
                             "Infill combination"),

    # ---------------- Speed (relative limits, see safety.py) ----------------
    "initial_layer_speed": _e("process", "speed", "float", "İlk katman hızı", "Initial layer speed",
                              min=5, max=500, unit="mm/s", rel="speed"),
    "initial_layer_infill_speed": _e("process", "speed", "float", "İlk katman dolgu hızı",
                                     "Initial layer infill speed", min=5, max=500,
                                     unit="mm/s", rel="speed"),
    "outer_wall_speed": _e("process", "speed", "float", "Dış duvar hızı", "Outer wall speed",
                           min=5, max=1000, unit="mm/s", rel="speed"),
    "inner_wall_speed": _e("process", "speed", "float", "İç duvar hızı", "Inner wall speed",
                           min=5, max=1000, unit="mm/s", rel="speed"),
    "sparse_infill_speed": _e("process", "speed", "float", "Dolgu hızı", "Sparse infill speed",
                              min=5, max=1000, unit="mm/s", rel="speed"),
    "internal_solid_infill_speed": _e("process", "speed", "float", "İç katı dolgu hızı",
                                      "Internal solid infill speed", min=5, max=1000,
                                      unit="mm/s", rel="speed"),
    "top_surface_speed": _e("process", "speed", "float", "Üst yüzey hızı", "Top surface speed",
                            min=5, max=1000, unit="mm/s", rel="speed"),
    "gap_infill_speed": _e("process", "speed", "float", "Boşluk dolgu hızı", "Gap infill speed",
                           min=5, max=1000, unit="mm/s", rel="speed"),
    "bridge_speed": _e("process", "speed", "float", "Köprü hızı", "Bridge speed",
                       min=5, max=500, unit="mm/s", rel="speed"),
    "support_speed": _e("process", "speed", "float", "Destek hızı", "Support speed",
                        min=5, max=1000, unit="mm/s", rel="speed"),
    "support_interface_speed": _e("process", "speed", "float", "Destek arayüz hızı",
                                  "Support interface speed", min=5, max=1000,
                                  unit="mm/s", rel="speed"),
    "default_acceleration": _e("process", "speed", "float", "Varsayılan ivme",
                               "Default acceleration", min=100, max=50000,
                               unit="mm/s²", rel="speed"),
    "outer_wall_acceleration": _e("process", "speed", "float", "Dış duvar ivmesi",
                                  "Outer wall acceleration", min=100, max=50000,
                                  unit="mm/s²", rel="speed"),
    "inner_wall_acceleration": _e("process", "speed", "float", "İç duvar ivmesi",
                                  "Inner wall acceleration", min=100, max=50000,
                                  unit="mm/s²", rel="speed"),
    "top_surface_acceleration": _e("process", "speed", "float", "Üst yüzey ivmesi",
                                   "Top surface acceleration", min=100, max=50000,
                                   unit="mm/s²", rel="speed"),
    "initial_layer_acceleration": _e("process", "speed", "float", "İlk katman ivmesi",
                                     "Initial layer acceleration", min=100, max=20000,
                                     unit="mm/s²", rel="speed"),
    "enable_overhang_speed": _e("process", "speed", "bool", "Sarkmada yavaşla",
                                "Slow down for overhangs"),

    # ---------------- Support ----------------
    "enable_support": _e("process", "support", "bool", "Destek", "Enable support"),
    "support_type": _e("process", "support", "enum", "Destek tipi", "Support type",
                       enum=["normal(auto)", "tree(auto)", "normal(manual)", "tree(manual)"]),
    "support_style": _e("process", "support", "enum", "Destek stili", "Support style",
                        enum=["default", "grid", "snug", "tree_slim", "tree_strong", "tree_hybrid"],
                        extra={"orca": ["organic"], "bambu": ["tree_organic"], "qidi": ["tree_organic"]}),
    "support_threshold_angle": _e("process", "support", "int", "Destek eşik açısı",
                                  "Support threshold angle", min=10, max=80, unit="°"),
    "support_on_build_plate_only": _e("process", "support", "bool", "Sadece tabladan destek",
                                      "Support on build plate only"),
    "support_critical_regions_only": _e("process", "support", "bool", "Sadece kritik bölgeler",
                                        "Support critical regions only"),
    "support_top_z_distance": _e("process", "support", "float", "Destek üst Z mesafesi",
                                 "Top Z distance", min=0.0, max=0.5, unit="mm"),
    "support_bottom_z_distance": _e("process", "support", "float", "Destek alt Z mesafesi",
                                    "Bottom Z distance", min=0.0, max=0.5, unit="mm"),
    "support_object_xy_distance": _e("process", "support", "float", "Destek-nesne XY mesafesi",
                                     "Support/object XY distance", min=0.1, max=2.0, unit="mm"),
    "support_interface_top_layers": _e("process", "support", "int", "Üst arayüz katmanı",
                                       "Top interface layers", min=0, max=10),
    "support_interface_bottom_layers": _e("process", "support", "int", "Alt arayüz katmanı",
                                          "Bottom interface layers", min=-1, max=10),
    "support_interface_spacing": _e("process", "support", "float", "Arayüz aralığı",
                                    "Interface spacing", min=0.0, max=2.0, unit="mm"),
    "support_base_pattern": _e("process", "support", "enum", "Destek deseni",
                               "Support base pattern",
                               enum=["default", "rectilinear", "rectilinear-grid", "honeycomb",
                                     "lightning", "hollow"]),
    "support_base_pattern_spacing": _e("process", "support", "float", "Destek desen aralığı",
                                       "Base pattern spacing", min=0.5, max=10.0, unit="mm"),
    "raft_layers": _e("process", "support", "int", "Raft katmanı", "Raft layers", min=0, max=10),
    "tree_support_branch_angle": _e("process", "support", "float", "Ağaç dal açısı",
                                    "Tree branch angle", min=10, max=60, unit="°"),
    "tree_support_branch_diameter": _e("process", "support", "float", "Ağaç dal çapı",
                                       "Tree branch diameter", min=1.0, max=10.0, unit="mm"),

    # ---------------- Others ----------------
    "skirt_loops": _e("process", "others", "int", "Etek (skirt) turu", "Skirt loops", min=0, max=10),
    "skirt_distance": _e("process", "others", "float", "Etek mesafesi", "Skirt distance",
                         min=0.0, max=60.0, unit="mm"),
    "brim_type": _e("process", "others", "enum", "Brim tipi", "Brim type",
                    enum=["auto_brim", "brim_ears", "outer_only", "inner_only",
                          "outer_and_inner", "no_brim"]),
    "brim_width": _e("process", "others", "float", "Brim genişliği", "Brim width",
                     min=0.0, max=20.0, unit="mm"),
    "brim_object_gap": _e("process", "others", "float", "Brim boşluğu", "Brim-object gap",
                          min=0.0, max=1.0, unit="mm"),
    "spiral_mode": _e("process", "others", "bool", "Vazo modu (spiral)", "Spiral vase mode"),

    # ---------------- Filament ----------------
    "nozzle_temperature": _e("filament", "filament", "int", "Nozul sıcaklığı",
                             "Nozzle temperature", min=150, max=350, unit="°C"),
    "nozzle_temperature_initial_layer": _e("filament", "filament", "int",
                                           "İlk katman nozul sıcaklığı",
                                           "Initial layer nozzle temperature",
                                           min=150, max=350, unit="°C"),
    "fan_min_speed": _e("filament", "filament", "float", "Fan en düşük", "Fan min speed",
                        min=0, max=100, unit="%"),
    "fan_max_speed": _e("filament", "filament", "float", "Fan en yüksek", "Fan max speed",
                        min=0, max=100, unit="%"),
    "overhang_fan_speed": _e("filament", "filament", "int", "Sarkma fanı", "Overhang fan speed",
                             min=0, max=100, unit="%"),
    "close_fan_the_first_x_layers": _e("filament", "filament", "int", "İlk katmanlarda fan kapalı",
                                       "No cooling for the first", min=0, max=10, unit="katman"),
    "slow_down_layer_time": _e("filament", "filament", "float", "Katman süresi alt sınırı",
                               "Min layer time", min=0, max=30, unit="s"),
    "filament_max_volumetric_speed": _e("filament", "filament", "float", "Maks. hacimsel akış",
                                        "Max volumetric speed", min=0.5, max=60,
                                        unit="mm³/s", rel="decrease_only"),
}

# Bed temperature keys depend on the plate type selected in Orca (curr_bed_type).
BED_TEMP_KEYS = {
    "Cool Plate": ("cool_plate_temp", "cool_plate_temp_initial_layer"),
    "Engineering Plate": ("eng_plate_temp", "eng_plate_temp_initial_layer"),
    "High Temp Plate": ("hot_plate_temp", "hot_plate_temp_initial_layer"),
    "Textured PEI Plate": ("textured_plate_temp", "textured_plate_temp_initial_layer"),
    "Textured Cool Plate": ("textured_cool_plate_temp", "textured_cool_plate_temp_initial_layer"),
    "Supertack Plate": ("supertack_plate_temp", "supertack_plate_temp_initial_layer"),
}
for _plate, (_k, _k0) in BED_TEMP_KEYS.items():
    SETTINGS[_k] = _e("filament", "filament", "int", "Tabla sıcaklığı", "Bed temperature",
                      min=0, max=120, unit="°C", rel="bed")
    SETTINGS[_k0] = _e("filament", "filament", "int", "İlk katman tabla sıcaklığı",
                       "Initial layer bed temperature", min=0, max=120, unit="°C", rel="bed")

# Read-only context keys (never written).
CONTEXT_KEYS_PRINTER = ["nozzle_diameter", "printer_model", "printable_height",
                        "printer_structure", "max_layer_height", "min_layer_height"]
CONTEXT_KEYS_FILAMENT = ["filament_type", "filament_vendor", "nozzle_temperature_range_low",
                         "nozzle_temperature_range_high", "filament_density",
                         "filament_settings_id"]


def enum_values(entry, flavor=None):
    """Enum values a slicer flavor accepts (None = OrcaSlicer, the plugin host)."""
    return list(entry.get("enum", [])) + list((entry.get("extra") or {}).get(flavor or "orca", []))


def label(key, lang="tr"):
    entry = SETTINGS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry["en"]


def page_label(page, lang="tr"):
    p = PAGES.get(page, {})
    return p.get(lang) or p.get("en") or page
