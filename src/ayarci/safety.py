"""3DsetuPia - safety filter. Nothing reaches OrcaSlicer without passing through here.

* only whitelisted keys (catalog.SETTINGS) - colours, painting, G-code, printer
  and multi-material settings are simply not in the list;
* every value is type-checked and clamped (hard limits + limits derived from the
  nozzle, the filament's own temperature range and the current preset);
* values are serialized exactly the way OrcaSlicer stores them.
"""

from .catalog import SETTINGS, BED_TEMP_KEYS, label, page_label, enum_values  # bundle:strip
from .rules import num, text  # bundle:strip

MAX_CHANGES = 45

ENUM_LABELS_TR = {
    "tree(auto)": "Ağaç (otomatik)", "normal(auto)": "Normal (otomatik)",
    "tree(manual)": "Ağaç (manuel)", "normal(manual)": "Normal (manuel)",
    "no ironing": "Ütüleme yok", "top": "Üst yüzeyler", "topmost": "Sadece en üst yüzey",
    "solid": "Tüm katı yüzeyler", "outer_only": "Sadece dış", "inner_only": "Sadece iç",
    "outer_and_inner": "Dış ve iç", "auto_brim": "Otomatik", "brim_ears": "Fare kulağı",
    "no_brim": "Brim yok", "aligned": "Hizalı", "nearest": "En yakın", "back": "Arka",
    "random": "Rastgele", "aligned_back": "Hizalı (arka)", "organic": "Organik",
    "snug": "Sıkı (snug)", "default": "Varsayılan", "classic": "Klasik", "arachne": "Arachne",
    "tree_organic": "Organik", "zig-zag": "Düz çizgi (rectilinear)", "monotonic": "Monotonik",
    "monotonicline": "Monotonik çizgi", "tree_hybrid": "Ağaç (hibrit)", "tree_slim": "Ağaç (ince)",
    "tree_strong": "Ağaç (güçlü)", "grid": "Izgara", "gyroid": "Gyroid", "cubic": "Kübik",
    "adaptivecubic": "Uyarlanır kübik", "lightning": "Yıldırım", "honeycomb": "Bal peteği",
    "inner wall/outer wall": "İç / dış", "outer wall/inner wall": "Dış / iç",
    "inner-outer-inner wall": "İç / dış / iç", "none": "Yok", "external": "Sadece dış", "all": "Hepsi",
}
ENUM_LABELS_EN = {
    "tree(auto)": "Tree (auto)", "normal(auto)": "Normal (auto)", "tree(manual)": "Tree (manual)",
    "normal(manual)": "Normal (manual)", "no ironing": "No ironing", "topmost": "Topmost only",
    "outer_only": "Outer only", "auto_brim": "Auto", "brim_ears": "Mouse ears", "no_brim": "No brim",
    "tree_organic": "Organic", "zig-zag": "Rectilinear", "tree_hybrid": "Tree (hybrid)",
    "tree_slim": "Tree (slim)", "tree_strong": "Tree (strong)", "adaptivecubic": "Adaptive cubic",
}


class Rejected(ValueError):
    pass


def _fmt_float(v):
    s = ("%.4f" % float(v)).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _parse_bool(v):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "on", "evet", "açık", "acik"):
        return True
    if s in ("0", "false", "no", "off", "hayır", "hayir", "kapalı", "kapali"):
        return False
    raise Rejected("not a boolean: %r" % (v,))


def _parse_number(v):
    if isinstance(v, bool):
        raise Rejected("boolean given for a number")
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower().replace("mm/s", "").replace("mm", "").replace("°c", "")
    s = s.replace("%", "").replace(",", ".").strip()
    try:
        return float(s.split()[0])
    except (ValueError, IndexError):
        raise Rejected("not a number: %r" % (v,))


def _vector_count(current):
    if current is None:
        return 1
    s = str(current)
    if "," in s:
        return len(s.split(","))
    return 1


def serialize(entry, value, current):
    count = _vector_count(current)
    t = entry["type"]
    if t == "bool":
        one = "1" if value else "0"
    elif t == "int":
        one = str(int(value))
    elif t == "percent":
        one = _fmt_float(value) + "%"
    elif t == "float":
        one = _fmt_float(value)
    else:
        one = str(value)
    return ",".join([one] * count) if count > 1 else one


def _limits(key, entry, ctx):
    lo, hi = entry.get("min"), entry.get("max")
    cur = ctx.get("current", {})
    printer = ctx.get("printer", {})
    fil = ctx.get("filament", {})
    d = num(printer.get("nozzle_diameter"), 0.4) or 0.4
    if key == "layer_height":
        lo = max(lo, num(printer.get("min_layer_height"), 0) or 0, round(d * 0.2, 3))
        hi = min(hi, round(d * 0.75, 3))
        mx = num(printer.get("max_layer_height"), 0) or 0
        if mx > 0:
            hi = min(hi, mx)
    elif key == "initial_layer_print_height":
        lo, hi = max(lo, round(d * 0.4, 3)), min(hi, round(d * 0.75, 3))
    elif key in ("nozzle_temperature", "nozzle_temperature_initial_layer"):
        rl = num(fil.get("nozzle_temperature_range_low"))
        rh = num(fil.get("nozzle_temperature_range_high"))
        c = num(cur.get(key))
        if rl and rh and rh > rl:
            lo, hi = max(lo, rl), min(hi, rh)
        elif c:
            lo, hi = max(lo, c - 15), min(hi, c + 15)
    rel = entry.get("rel")
    c = num(cur.get(key))
    if rel == "speed" and c:
        hi = min(hi, c * 1.3)
        lo = max(lo, c * 0.3)
    elif rel == "decrease_only" and c:
        hi = min(hi, c)
    elif rel == "bed" and c is not None:
        lo, hi = max(lo, c - 15), min(hi, c + 15)
    return lo, hi


def _display(entry, serialized, lang):
    if serialized is None:
        return "—"
    first = str(serialized).split(",")[0]
    t = entry["type"]
    if t == "bool":
        on = first.strip() in ("1", "true")
        return ("Açık" if on else "Kapalı") if lang == "tr" else ("On" if on else "Off")
    if t == "enum":
        table = ENUM_LABELS_TR if lang == "tr" else ENUM_LABELS_EN
        return table.get(first, first)
    unit = entry.get("unit", "")
    if t == "percent" or unit == "%":
        return first if first.endswith("%") else first + "%"
    return (first + " " + unit).strip()


def allowed_keys(ctx):
    """Keys the AI may touch in this context (bed keys only for the active plate)."""
    bed_type = ctx.get("bed_type") or ""
    active_bed = set(BED_TEMP_KEYS.get(bed_type, ()))
    all_bed = {k for pair in BED_TEMP_KEYS.values() for k in pair}
    keys = []
    for k in SETTINGS:
        if k in all_bed and k not in active_bed:
            continue
        keys.append(k)
    return keys


def validate(proposals, ctx, source="rules"):
    """proposals: [{"key", "value", "reason": str|{"tr","en"}}] -> (changes, rejected)."""
    lang = ctx.get("lang", "tr")
    cur = ctx.get("current", {})
    allowed = set(allowed_keys(ctx))
    merged = {}
    rejected = []
    for p in proposals or []:
        if not isinstance(p, dict):
            continue
        key = str(p.get("key", "")).strip()
        if key not in allowed:
            rejected.append({"key": key, "why": "not allowed"})
            continue
        entry = SETTINGS[key]
        if key not in cur or cur.get(key) is None:
            rejected.append({"key": key, "why": "not present in active preset"})
            continue
        raw = p.get("value")
        note = ""
        try:
            if entry["type"] == "bool":
                value = _parse_bool(raw)
            elif entry["type"] == "enum":
                s = str(raw).strip()
                options = enum_values(entry, ctx.get("flavor")) + [str(cur.get(key))]
                match = [e for e in options if e.lower() == s.lower()]
                if not match:
                    raise Rejected("unknown option %r" % s)
                value = match[0]
            else:
                value = _parse_number(raw)
                lo, hi = _limits(key, entry, ctx)
                if lo is not None and hi is not None and lo > hi:
                    raise Rejected("no safe range")
                clamped = value
                if lo is not None:
                    clamped = max(lo, clamped)
                if hi is not None:
                    clamped = min(hi, clamped)
                if entry["type"] == "int":
                    clamped = int(round(clamped))
                    if hi is not None and clamped > hi:
                        clamped = int(hi)
                    if lo is not None and clamped < lo:
                        clamped = int(-(-lo // 1))
                if abs(clamped - value) > 1e-9:
                    note = " (güvenli sınıra çekildi)" if lang == "tr" else " (clamped to a safe limit)"
                value = clamped
        except Rejected as exc:
            rejected.append({"key": key, "why": str(exc)})
            continue
        new = serialize(entry, value, cur.get(key))
        if _same(entry, new, cur.get(key)):
            continue
        reason = p.get("reason", "")
        if isinstance(reason, dict):
            reason = reason.get(lang) or reason.get("en") or ""
        merged[key] = {
            "key": key,
            "cat": entry["cat"],
            "page": entry["page"],
            "page_label": page_label(entry["page"], lang),
            "label": label(key, lang),
            "old": cur.get(key),
            "new": new,
            "old_display": _display(entry, cur.get(key), lang),
            "new_display": _display(entry, new, lang),
            "reason": (str(reason).strip()[:300] + note).strip(),
            "source": p.get("source", source),
        }
    _consistency(merged, cur)
    order = {k: i for i, k in enumerate(SETTINGS)}
    changes = sorted(merged.values(), key=lambda c: order.get(c["key"], 9999))[:MAX_CHANGES]
    for i, c in enumerate(changes):
        c["id"] = i
    return changes, rejected


def _same(entry, a, b):
    if b is None:
        return False
    if entry["type"] in ("float", "int", "percent"):
        try:
            return abs(_parse_number(str(a).split(",")[0]) - _parse_number(str(b).split(",")[0])) < 1e-6 \
                and _vector_count(a) == _vector_count(b)
        except Rejected:
            return False
    if entry["type"] == "bool":
        try:
            return _parse_bool(str(a).split(",")[0]) == _parse_bool(str(b).split(",")[0])
        except Rejected:
            return False
    return str(a).strip() == str(b).strip()


def _final(merged, cur, key):
    if key in merged:
        return merged[key]["new"]
    return cur.get(key)


def _consistency(merged, cur):
    if text(_final(merged, cur, "ironing_type")) in ("", "no ironing"):
        for k in ("ironing_pattern", "ironing_flow", "ironing_spacing", "ironing_speed"):
            merged.pop(k, None)
    if num(_final(merged, cur, "enable_support"), 0) != 1:
        for k in list(merged):
            if k.startswith("support_") or k.startswith("tree_support_"):
                merged.pop(k, None)
    if text(_final(merged, cur, "brim_type")) == "no_brim":
        merged.pop("brim_width", None)
        merged.pop("brim_object_gap", None)
