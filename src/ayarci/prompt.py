"""3DsetuPia - builds the single request sent to the AI.

Only measurements and settings are sent. The 3D model itself never leaves the PC.
"""

import json

from .catalog import SETTINGS, PAGES, enum_values  # bundle:strip
from .safety import allowed_keys, _limits  # bundle:strip

INTENT_TEXT = {
    "balanced": "balanced: good quality, reasonable strength and time",
    "looks": "looks: best visual surface quality, time is less important",
    "strength": "strength: functional part, maximise strength and durability",
    "speed": "speed: shortest reasonable print time, acceptable quality",
}

SYSTEM_PROMPT = """You are an expert FDM 3D-printing process engineer working with a slicer
(OrcaSlicer, Bambu Studio, QIDI Studio or a relative).
The user is NOT an expert. They loaded a model, picked a filament and a goal, and want you
to tune the slicer settings for THIS model so the print succeeds on the first try.

You receive: measurements of the model (computed locally), the printer, the filament,
the user's goal and note, the CURRENT value of every setting you may change (with its
allowed type and range), and suggestions from a local rule engine.

Your job:
- Go through every settings page (quality, strength, speed, support, others, filament)
  and decide what should change for this specific model, printer, filament and goal.
- Change only what genuinely helps. Keep good existing values. Prefer the printer
  profile's tuned speeds; lower them when the model needs it (tall/thin parts, fine
  details, flexible filament, looks goal) and raise them only modestly for the speed goal.
- Rule-engine suggestions are a starting point: keep, adjust or drop them.
- Never touch colours, painting, multi-material, G-code, printer/machine settings.
  Only keys from the provided list are accepted; anything else is discarded.
- Values must respect the given type and range. Enum values must be copied exactly.
  Percent values like "20%". Booleans "1" or "0". Numbers without units.
- Write each reason as one short, friendly sentence a beginner understands
  (max ~20 words), in the requested language.

Answer with JSON only, exactly in this shape:
{"summary": "<2-3 sentences for the user about the model and your plan>",
 "changes": [{"key": "<setting key>", "value": "<new value as string>", "reason": "<why>"}]}
At most 30 changes."""


def settings_table(ctx):
    cur = ctx.get("current", {})
    rows = {}
    for key in allowed_keys(ctx):
        if key not in cur or cur.get(key) is None:
            continue
        e = SETTINGS[key]
        row = {"page": e["page"], "type": e["type"], "current": cur.get(key).split(",")[0]
               if isinstance(cur.get(key), str) else cur.get(key)}
        if e["type"] == "enum":
            row["options"] = enum_values(e, ctx.get("flavor"))
        elif e["type"] != "bool":
            lo, hi = _limits(key, e, ctx)
            if lo is not None:
                row["min"] = round(lo, 3)
            if hi is not None:
                row["max"] = round(hi, 3)
            if e.get("unit"):
                row["unit"] = e["unit"]
        rows[key] = row
    return rows


def build_messages(analysis, ctx, baseline):
    lang = ctx.get("lang", "tr")
    payload = {
        "answer_language": "Turkish" if lang == "tr" else "English",
        "goal": INTENT_TEXT.get(ctx.get("intent"), INTENT_TEXT["balanced"]),
        "user_note": (ctx.get("note") or "")[:500],
        "printer": ctx.get("printer", {}),
        "filament": ctx.get("filament", {}),
        "bed_type": ctx.get("bed_type"),
        "model_measurements": {
            "summary": analysis.get("summary", {}),
            "objects": analysis.get("objects", [])[:8],
            "notes": {
                "overhang.below_30deg_mm2": "downward area flatter than 30 deg from horizontal (needs support unless bridging)",
                "slenderness": "height / smallest XY size",
                "tipping_index": "height / sqrt(bed contact area); >6 means tipping/lifting risk",
                "organic_score": "0 = boxy/mechanical, 1 = curved/sculpted",
                "wall_thickness_mm": "sampled local wall thickness percentiles",
                "topmost_flat_mm2": "flat area at the very top (ironing candidate)",
            },
        },
        "settings_you_may_change": settings_table(ctx),
        "rule_engine_suggestions": [
            {"key": b["key"], "value": str(b["value"]),
             "reason": b["reason"].get("en") if isinstance(b.get("reason"), dict) else b.get("reason")}
            for b in baseline
        ],
        "pages": {k: v["en"] for k, v in PAGES.items()},
    }
    user = ("Tune the slicer settings for this print.\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=1))
    return SYSTEM_PROMPT, user


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["key", "value", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "changes"],
    "additionalProperties": False,
}


def parse_response(text):
    """Extract the JSON object from a model reply (tolerates code fences and chatter)."""
    if text is None:
        raise ValueError("empty AI response")
    s = str(text).strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI response contained no JSON object")
    data = json.loads(s[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("AI response is not an object")
    changes = data.get("changes") or []
    if not isinstance(changes, list):
        raise ValueError("'changes' is not a list")
    clean = []
    for c in changes:
        if isinstance(c, dict) and "key" in c and "value" in c:
            clean.append({"key": str(c["key"]), "value": c["value"],
                          "reason": str(c.get("reason", ""))})
    return {"summary": str(data.get("summary", "")).strip(), "changes": clean}
