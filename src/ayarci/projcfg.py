"""3DsetuPia - reading and writing settings in a slicer project config.

Bambu Studio, QIDI Studio and OrcaSlicer store the full configuration of a
project in Metadata/project_settings.config as a flat JSON object. Most values
are strings; many are lists:

* process keys on multi-nozzle printers (H2D/H2C) hold one value per
  extruder/nozzle variant (print_extruder_id / print_extruder_variant);
* filament keys hold one value per filament slot, and on multi-nozzle printers
  some hold one value per slot and variant (filament_self_index tells which
  entry belongs to which slot).

This module turns that into the plain "current value" dictionary the rule
engine, the AI prompt and the safety filter work with, and writes validated
changes back without disturbing the values of other slots or variants.
"""

from .catalog import SETTINGS, CONTEXT_KEYS_PRINTER, CONTEXT_KEYS_FILAMENT  # bundle:strip
from .rules import num  # bundle:strip


def _as_list(value):
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _fmt_number(x, like):
    """Format x the way the neighbouring value `like` is written ("15%", "0.2", "200")."""
    s = ("%.4f" % float(x)).rstrip("0").rstrip(".")
    if s in ("", "-0"):
        s = "0"
    if str(like).strip().endswith("%"):
        s += "%"
    return s


class ProjectConfig:
    """Wraps a flat project config dict (modified in place by apply())."""

    def __init__(self, cfg, filament_index=0, filament_map=None):
        self.cfg = cfg
        self.filament_count = max(1, len(_as_list(cfg.get("filament_settings_id"))))
        self.filament_index = min(max(0, int(filament_index)), self.filament_count - 1)
        self.filament_map = filament_map   # plate-level map wins over the global one

    # ---------------------------------------------------------------- indices
    def extruder_of_filament(self):
        """1-based physical extruder used by the chosen filament (1 on single-nozzle printers)."""
        fmap = self.filament_map or _as_list(self.cfg.get("filament_map"))
        if len(fmap) == self.filament_count:
            try:
                return max(1, int(float(fmap[self.filament_index])))
            except ValueError:
                pass
        return 1

    def _variant_of_extruder(self, ext):
        types = _as_list(self.cfg.get("extruder_type"))
        vols = _as_list(self.cfg.get("nozzle_volume_type"))
        if ext - 1 < len(types) and ext - 1 < len(vols):
            return "%s %s" % (types[ext - 1], vols[ext - 1])
        return None

    def process_index(self):
        """Index into per-variant process lists for the extruder/nozzle the chosen filament prints with."""
        ids = _as_list(self.cfg.get("print_extruder_id"))
        variants = _as_list(self.cfg.get("print_extruder_variant"))
        if len(ids) <= 1:
            return 0
        ext = self.extruder_of_filament()
        want = self._variant_of_extruder(ext)
        first = None
        for i, eid in enumerate(ids):
            if str(eid) != str(ext):
                continue
            if first is None:
                first = i
            if want and i < len(variants) and variants[i] == want:
                return i
        return first or 0

    def filament_indices(self, length):
        """Entries of a filament list of `length` that belong to the chosen slot."""
        n = self.filament_count
        if length == n:
            return [self.filament_index]
        owners = _as_list(self.cfg.get("filament_self_index"))
        if len(owners) == length:
            mine = [i for i, o in enumerate(owners) if str(o) == str(self.filament_index + 1)]
            if mine:
                return mine
        if length and length % n == 0:
            k = length // n
            return list(range(self.filament_index * k, (self.filament_index + 1) * k))
        return [0] if length else []

    def _active_filament_entry(self, length):
        idx = self.filament_indices(length)
        if len(idx) <= 1:
            return idx[0] if idx else 0
        owners_variants = _as_list(self.cfg.get("filament_extruder_variant"))
        want = self._variant_of_extruder(self.extruder_of_filament())
        if want and len(owners_variants) == length:
            for i in idx:
                if owners_variants[i] == want:
                    return i
        return idx[0]

    # ---------------------------------------------------------------- reading
    def value(self, key, cat=None):
        """Current value (one string) of a setting for the chosen filament and extruder."""
        if key not in self.cfg:
            return None
        v = self.cfg[key]
        if not isinstance(v, list):
            return None if v is None else str(v)
        if not v:
            return None
        if cat is None:
            cat = SETTINGS.get(key, {}).get("cat")
        if cat == "filament":
            i = self._active_filament_entry(len(v))
        elif cat == "process":
            i = self.process_index()
        else:  # printer/context keys: per extruder
            i = self.extruder_of_filament() - 1
        return str(v[i] if 0 <= i < len(v) else v[0])

    def current(self):
        out = {}
        for key, entry in SETTINGS.items():
            val = self.value(key, entry["cat"])
            if val is not None:
                out[key] = val
        return out

    def printer_info(self):
        info = {}
        for k in CONTEXT_KEYS_PRINTER:
            val = self.value(k, "printer")
            if val is not None:
                info[k] = val
        info["preset"] = str(self.cfg.get("printer_settings_id") or "")
        return info

    def filament_info(self):
        info = {}
        for k in CONTEXT_KEYS_FILAMENT:
            val = self.value(k, "filament")
            if val is not None:
                info[k] = val
        names = _as_list(self.cfg.get("filament_settings_id"))
        info["preset"] = names[self.filament_index] if self.filament_index < len(names) else ""
        return info

    def context(self, lang="tr", intent="balanced", note=""):
        return {"lang": lang, "intent": intent, "note": note, "current": self.current(),
                "printer": self.printer_info(), "filament": self.filament_info(),
                "bed_type": str(self.cfg.get("curr_bed_type") or "")}

    # ---------------------------------------------------------------- writing
    def apply(self, changes):
        """Write validated changes (safety.validate output). Returns the keys written."""
        done = []
        touched = {"process": set(), "filament": set()}
        for c in changes:
            key, new, cat = c["key"], str(c["new"]), c["cat"]
            if key not in self.cfg:
                continue
            old = self.cfg[key]
            if not isinstance(old, list):
                self.cfg[key] = new
            else:
                self.cfg[key] = self._write_list(key, old, new, cat)
            touched[cat].add(key)
            done.append(key)
        self._mark_different(touched)
        return done

    def _write_list(self, key, old, new, cat):
        out = list(old)
        if cat == "filament":
            indices = self.filament_indices(len(out))
            anchor = self._active_filament_entry(len(out))
        else:
            indices = list(range(len(out)))
            anchor = self.process_index()
        entry = SETTINGS.get(key, {})
        numeric = entry.get("type") in ("int", "float", "percent")
        a_old = num(out[anchor]) if 0 <= anchor < len(out) else None
        a_new = num(new)
        for i in indices:
            if not numeric or a_old is None or a_new is None or num(out[i]) is None or num(out[i]) == a_old:
                out[i] = new
                continue
            # other variants keep their own tuning: same step in degrees, same ratio otherwise
            o = num(out[i])
            if entry.get("unit") == "°C":
                v = o + (a_new - a_old)
            elif a_old:
                v = o * (a_new / a_old)
            else:
                v = a_new
            if entry.get("type") == "int":
                v = int(round(v))
            out[i] = _fmt_number(v, out[i])
        return out

    def _mark_different(self, touched):
        """Keep different_settings_to_system in step: [process, filament 1..n, printer]."""
        diff = self.cfg.get("different_settings_to_system")
        if not isinstance(diff, list) or len(diff) != self.filament_count + 2:
            return
        slots = {"process": 0, "filament": 1 + self.filament_index}
        for cat, keys in touched.items():
            if not keys:
                continue
            i = slots[cat]
            have = {k for k in str(diff[i] or "").split(";") if k}
            diff[i] = ";".join(sorted(have | keys))
