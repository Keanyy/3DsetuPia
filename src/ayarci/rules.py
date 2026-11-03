"""3DsetuPia - local rule engine.

Works with no AI at all ("Yerel kurallar" mode) and also gives the AI a
reasoned baseline. Every proposal still goes through safety.validate().
"""

import math

INTENTS = ("balanced", "looks", "strength", "speed")

WARPING = ("ABS", "ASA", "PC", "PA", "PA-CF", "PA6", "PA12", "PAHT", "PET-CF", "PP", "PPS", "PEI",
           "PEEK", "HIPS", "PC-ABS", "ABS-GF", "ASA-CF", "PA-GF", "PPA")
FLEXIBLE = ("TPU", "TPE", "TPU-AMS", "PEBA", "FLEX")


def num(value, default=None):
    """First number of an Orca serialized value ('200', '200,200', '15%', 'nil')."""
    if value is None:
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    s = str(value).strip().split(",")[0].split(";")[0].strip().rstrip("%")
    try:
        return float(s)
    except ValueError:
        return default


def text(value):
    if value is None:
        return ""
    return str(value).split(";")[0].split(",")[0].strip().strip('"')


def filament_family(ftype):
    t = (ftype or "").upper().strip()
    if any(t.startswith(f) for f in FLEXIBLE):
        return "flex"
    if t.startswith("PETG") or t.startswith("PCTG") or t == "PET":
        return "petg"
    if any(t == w or t.startswith(w + "-") or t.startswith(w + " ") for w in WARPING) or t in WARPING:
        return "warping"
    if t.startswith("PLA") or t == "" or t.startswith("PVB"):
        return "pla"
    return "other"


class _Out:
    def __init__(self, lang):
        self.lang = lang
        self.items = {}

    def add(self, key, value, tr, en):
        self.items[key] = {"key": key, "value": value, "reason": {"tr": tr, "en": en}}

    def list(self):
        return list(self.items.values())


def _round_layer(x, d):
    step = 0.02 if d >= 0.3 else 0.01
    return round(round(x / step) * step, 3)


def propose(analysis, ctx):
    """analysis: geometry.analyze_plate() result. ctx: see module docstring of plugin.py."""
    out = _Out(ctx.get("lang", "tr"))
    summary = analysis.get("summary") or {}
    objects = analysis.get("objects") or []
    if not objects:
        return []
    tags = set(summary.get("tags", []))
    intent = ctx.get("intent") if ctx.get("intent") in INTENTS else "balanced"
    cur = ctx.get("current", {})
    printer = ctx.get("printer", {})
    fil = ctx.get("filament", {})
    d = num(printer.get("nozzle_diameter"), 0.4) or 0.4
    fam = filament_family(fil.get("filament_type"))
    note = (ctx.get("note") or "").lower()

    lh_cur = num(cur.get("layer_height"), 0.2)

    # ---------------- Layer height ----------------
    factor = {"looks": 0.3, "balanced": None, "strength": 0.5, "speed": 0.7}[intent]
    lh = lh_cur if factor is None else _round_layer(d * factor, d)
    detail = "thin_features" in tags or (summary.get("min_object_size_mm") or 99) < 12
    if detail:
        lh = min(lh, _round_layer(d * 0.3, d))
    lh = max(_round_layer(d * 0.25, d), min(lh, _round_layer(d * 0.7, d)))
    if abs(lh - lh_cur) >= 0.005:
        if detail:
            out.add("layer_height", lh,
                    "Modelde ince detaylar var; daha ince katman detayları korur.",
                    "The model has fine details; thinner layers keep them.")
        elif intent == "looks":
            out.add("layer_height", lh, "Görünüş öncelikli: ince katman yüzeydeki çizgileri azaltır.",
                    "Looks first: thinner layers reduce visible layer lines.")
        elif intent == "speed":
            out.add("layer_height", lh, "Hız öncelikli: kalın katman baskı süresini kısaltır.",
                    "Speed first: thicker layers shorten print time.")
        else:
            out.add("layer_height", lh, "Dayanıklılık için nozula uygun standart katman.",
                    "Standard layer height for this nozzle, good for strength.")

    # ---------------- Walls / shells / infill ----------------
    walls_cur = int(num(cur.get("wall_loops"), 2) or 2)
    walls = {"looks": max(walls_cur, 3), "balanced": max(walls_cur, 2),
             "strength": max(walls_cur, 5), "speed": 2}[intent]
    if "tall_thin" in tags and walls < 3:
        walls = 3
    if "functional" in note or "dayan" in note or "vida" in note or "screw" in note:
        walls = max(walls, 4)
    if walls != walls_cur:
        out.add("wall_loops", walls,
                {"strength": "Dayanıklılık için daha fazla duvar; parçanın gücünün çoğu duvarlardan gelir.",
                 "speed": "Hız öncelikli: 2 duvar çoğu parça için yeterli.",
                 "looks": "3 duvar dolgunun yüzeyden görünmesini engeller.",
                 "balanced": "İnce/uzun parça için en az 3 duvar sağlamlık verir."}[intent],
                {"strength": "More walls for strength; most part strength comes from walls.",
                 "speed": "Speed first: 2 walls are enough for most parts.",
                 "looks": "3 walls stop infill from showing through.",
                 "balanced": "At least 3 walls keep a tall/thin part stiff."}[intent])

    top_mm = {"looks": 1.0, "balanced": 0.8, "strength": 1.2, "speed": 0.6}[intent]
    bot_mm = {"looks": 0.6, "balanced": 0.6, "strength": 1.0, "speed": 0.5}[intent]
    top_n = max(3, math.ceil(top_mm / lh - 1e-6))
    bot_n = max(2, math.ceil(bot_mm / lh - 1e-6))
    def _shell_change(cur_n, want):
        # speed intent may thin the shells; every other intent only thickens them
        return cur_n > want if intent == "speed" else cur_n < want
    if _shell_change(int(num(cur.get("top_shell_layers"), top_n)), top_n):
        out.add("top_shell_layers", top_n,
                "Seçilen katman yüksekliğinde üst yüzeyin kapalı ve düzgün çıkması için.",
                "Keeps the top surface closed and smooth at this layer height.")
    if _shell_change(int(num(cur.get("bottom_shell_layers"), bot_n)), bot_n):
        out.add("bottom_shell_layers", bot_n, "Alt yüzey için yeterli kalınlık.",
                "Enough thickness for the bottom surface.")

    dens_cur = num(cur.get("sparse_infill_density"), 15)
    dens = {"looks": 12, "balanced": max(10, dens_cur), "strength": 40, "speed": 10}[intent]
    if "tall_thin" in tags:
        dens = max(dens, 20)
    if abs(dens - dens_cur) >= 1:
        out.add("sparse_infill_density", dens,
                "Dayanıklılık için yüksek dolgu." if intent == "strength" else
                ("Uzun ve ince parçada sağlamlık için." if "tall_thin" in tags else
                 "Bu amaç için yeterli dolgu; gereksiz malzeme ve süre harcanmaz."),
                "Higher infill for strength." if intent == "strength" else
                ("Stiffness for a tall, thin part." if "tall_thin" in tags else
                 "Enough infill for this goal without wasting material and time."))
    pat_cur = text(cur.get("sparse_infill_pattern"))
    if (intent == "strength" or "tall_thin" in tags) and pat_cur not in ("gyroid", "cubic", "adaptivecubic", "tpmsd"):
        out.add("sparse_infill_pattern", "gyroid",
                "Gyroid her yönde dayanıklıdır ve uzun parçalarda titreşimi azaltır.",
                "Gyroid is strong in every direction and damps wobble on tall parts.")

    # ---------------- Thin features ----------------
    if "thin_features" in tags and text(cur.get("wall_generator")) != "arachne":
        out.add("wall_generator", "arachne",
                "İnce bölümler var; Arachne değişken genişlikle bu bölümleri boşluksuz basar.",
                "Thin sections found; Arachne fills them with variable line width.")

    # ---------------- Surface quality ----------------
    if intent == "looks":
        if summary.get("max_topmost_flat_mm2", 0) >= 300 and text(cur.get("ironing_type")) in ("", "no ironing"):
            out.add("ironing_type", "top",
                    "Geniş düz üst yüzey var; ütüleme pürüzsüz ve parlak bir yüzey verir (süre biraz artar).",
                    "Large flat top surface; ironing makes it smooth (adds some time).")
        if text(cur.get("seam_position")) in ("nearest", "random"):
            out.add("seam_position", "aligned", "Dikiş izini tek bir çizgide toplar, daha temiz görünür.",
                    "Lines the seam up in one place for a cleaner look.")
        if text(cur.get("top_surface_pattern")) in ("zig-zag", "rectilinear", "alignedrectilinear"):
            out.add("top_surface_pattern", "monotonic", "Monotonic desen üst yüzeyde daha düzgün görünür.",
                    "Monotonic gives a more even top surface.")
        for k in ("outer_wall_speed", "top_surface_speed"):
            v = num(cur.get(k))
            if v and v > 120:
                out.add(k, round(max(60.0, v * 0.6)),
                        "Görünüş için dış yüzeyi yavaş basmak çizgi ve titreşim izlerini azaltır.",
                        "Slower outer surfaces reduce ringing and lines.")

    # ---------------- Supports ----------------
    ov = summary.get("total_overhang_below_30deg_mm2", 0.0)
    sup_on = num(cur.get("enable_support"), 0) == 1
    organic = summary.get("mean_organic_score", 0.0) >= 0.4
    if "needs_support" in tags:
        if not sup_on:
            out.add("enable_support", True,
                    "Modelde desteksiz basılamayacak sarkmalar var (%d mm²)." % ov,
                    "The model has overhangs that cannot print unsupported (%d mm²)." % ov)
        stype = "tree(auto)" if organic else "normal(auto)"
        if text(cur.get("support_type")) != stype:
            out.add("support_type", stype,
                    "Kavisli/organik model: ağaç destek daha az malzeme harcar ve kolay sökülür." if organic
                    else "Düz ve köşeli sarkmalar: normal destek bu yüzeyleri daha iyi taşır.",
                    "Curved/organic model: tree supports use less material and remove easily." if organic
                    else "Flat, boxy overhangs: normal supports hold them better.")
        organic_style = "organic" if ctx.get("flavor") in (None, "orca") else "tree_organic"
        style = organic_style if organic else "snug"
        if text(cur.get("support_style")) not in (style,):
            out.add("support_style", style,
                    "Bu model tipine uygun destek stili.", "Support style that suits this model type.")
        if intent == "looks" and int(num(cur.get("support_interface_top_layers"), 2)) < 3:
            out.add("support_interface_top_layers", 3,
                    "Desteğe oturan yüzeyin daha düzgün çıkması için.",
                    "Smoother surface where the part rests on supports.")
    elif "self_supporting" in tags and sup_on:
        out.add("enable_support", False,
                "Model kendini taşıyor; destek gereksiz süre ve malzeme harcar.",
                "The model is self-supporting; supports would only waste time and material.")

    # ---------------- Bed adhesion ----------------
    brim_cur = text(cur.get("brim_type"))
    tall_risk = "tipping_risk" in tags or "small_base" in tags
    warp_risk = fam == "warping" and ("large_footprint" in tags or summary.get("max_footprint_mm", 0) >= 100)
    if tall_risk or warp_risk:
        width = 8.0 if (summary.get("max_tipping_index", 0) >= 12 or warp_risk) else 5.0
        if brim_cur not in ("outer_only", "outer_and_inner", "brim_ears"):
            out.add("brim_type", "outer_only",
                    "Tabana temas alanı küçük ya da parça uzun; brim devrilmeyi ve kalkmayı önler." if tall_risk
                    else "Bu filament çekmeye yatkın ve parça geniş; brim köşelerin kalkmasını önler.",
                    "Small bed contact or a tall part; a brim prevents tipping and lifting." if tall_risk
                    else "This filament tends to warp and the part is large; a brim stops corners lifting.")
        if num(cur.get("brim_width"), 0) < width:
            out.add("brim_width", width, "Yeterli tutunma için brim genişliği.",
                    "Brim width for enough grip.")

    # ---------------- Filament-specific ----------------
    fan_max = num(cur.get("fan_max_speed"))
    fan_min = num(cur.get("fan_min_speed"))
    if fam == "petg":
        if fan_max is not None and fan_max > 60:
            out.add("fan_max_speed", 50, "PETG'de güçlü fan katman bağını zayıflatır.",
                    "Strong cooling weakens PETG layer bonding.")
        if fan_min is not None and fan_min > 40:
            out.add("fan_min_speed", 30, "PETG için daha düşük temel soğutma.", "Lower base cooling for PETG.")
    elif fam == "warping":
        if fan_max is not None and fan_max > 40:
            out.add("fan_max_speed", 30, "Bu filament hızlı soğuyunca çatlar/kalkar; fan düşük olmalı.",
                    "This filament cracks or warps when cooled fast; keep the fan low.")
        if fan_min is not None and fan_min > 15:
            out.add("fan_min_speed", 10, "Çatlamayı önlemek için düşük soğutma.", "Low cooling to avoid cracking.")
        if num(cur.get("close_fan_the_first_x_layers"), 1) < 3:
            out.add("close_fan_the_first_x_layers", 3, "İlk katmanlar tablaya iyi yapışsın diye fan kapalı.",
                    "Fan off on the first layers for better bed adhesion.")
    elif fam == "pla":
        if "needs_support" in tags or summary.get("max_overhang_ratio", 0) > 0.03:
            if num(cur.get("overhang_fan_speed"), 100) < 100:
                out.add("overhang_fan_speed", 100, "PLA sarkmalarda tam fanla daha temiz çıkar.",
                        "PLA overhangs come out cleaner with full fan.")
    elif fam == "flex":
        for k, cap in (("outer_wall_speed", 25), ("inner_wall_speed", 30), ("sparse_infill_speed", 35),
                       ("internal_solid_infill_speed", 30), ("top_surface_speed", 25),
                       ("initial_layer_speed", 15)):
            v = num(cur.get(k))
            if v and v > cap:
                out.add(k, cap, "Esnek filament (TPU) yavaş basılmazsa sıkışır.",
                        "Flexible filament (TPU) jams unless printed slowly.")

    if intent == "strength" and fam in ("pla", "petg"):
        t = num(cur.get("nozzle_temperature"))
        hi = num(fil.get("nozzle_temperature_range_high"))
        if t and hi and t + 5 <= hi:
            out.add("nozzle_temperature", int(t + 5), "Biraz daha sıcak baskı katmanların birbirine daha iyi kaynamasını sağlar.",
                    "A slightly hotter print improves layer bonding.")

    # ---------------- Tall/thin stability ----------------
    if "tall_thin" in tags and summary.get("max_slenderness", 0) >= 5:
        for k in ("outer_wall_acceleration", "inner_wall_acceleration"):
            v = num(cur.get(k))
            if v and v > 3000:
                out.add(k, round(v * 0.6), "Uzun ince parça sallanmasın diye ivme düşürüldü.",
                        "Lower acceleration so the tall, thin part does not wobble.")

    return out.list()
