"""3DsetuPia - printer, process and filament profiles of the slicers installed on this PC.

Bambu Studio, QIDI Studio, OrcaSlicer and other slicers of the same family keep
their profile library as JSON files (system/<Vendor>.json lists them, each
profile "inherits" from a parent). 3DsetuPia reads them to offer the printers the
user has set up, and to build the complete settings of a project for another
printer from the manufacturer's own profiles (machine settings and G-code are
copied as they are, never invented).
"""

import glob
import json
import os
import re

from .catalog import BED_TEMP_KEYS  # bundle:strip
from .rules import num  # bundle:strip

KNOWN_SLICERS = [
    # id, label, data folder (in %APPDATA%), app name in 3MF files, executable (in Program Files)
    ("bambu", "Bambu Studio", "BambuStudio", "BambuStudio", r"Bambu Studio\bambu-studio.exe"),
    ("qidi", "QIDI Studio", "QIDIStudio", "QIDIStudio", r"QIDIStudio\qidi-studio.exe"),
    ("orca", "OrcaSlicer", "OrcaSlicer", "OrcaSlicer", r"OrcaSlicer\orca-slicer.exe"),
    ("snapmaker", "Snapmaker Orca", "Snapmaker_Orca", "Snapmaker_Orca", r"Snapmaker_Orca\snapmaker-orca.exe"),
    ("elegoo", "Elegoo Slicer", "ElegooSlicer", "ElegooSlicer", r"ElegooSlicer\elegoo-slicer.exe"),
    ("anycubic", "Anycubic Slicer Next", "AnycubicSlicerNext", "AnycubicSlicerNext",
     r"AnycubicSlicerNext\AnycubicSlicerNext.exe"),
]

META_KEYS = {"name", "inherits", "from", "instantiation", "type", "setting_id", "base_id", "version",
             "compatible_printers", "compatible_printers_condition", "compatible_prints",
             "compatible_prints_condition", "is_custom_defined", "renamed_from", "description", "box_id",
             "filament_id", "user_id", "updated_time", "sync_info", "url", "force_update"}


# Filament settings that Bambu-family slicers keep once per nozzle variant ("Direct Drive Standard",
# "Direct Drive High Flow"...). Taken from a Bambu Studio 2.5 H2C project (filament_self_index).
VARIANT_FILAMENT_KEYS = {
    "filament_adaptive_volumetric_speed", "filament_bridge_speed", "filament_cooling_before_tower",
    "filament_deretraction_speed", "filament_enable_overhang_speed", "filament_flow_ratio", "filament_flush_temp",
    "filament_flush_volumetric_speed", "filament_long_retractions_when_cut", "filament_max_volumetric_speed",
    "filament_overhang_1_4_speed", "filament_overhang_2_4_speed", "filament_overhang_3_4_speed",
    "filament_overhang_4_4_speed", "filament_overhang_totally_speed", "filament_pre_cooling_temperature",
    "filament_pre_cooling_temperature_nc", "filament_ramming_travel_time", "filament_ramming_travel_time_nc",
    "filament_ramming_volumetric_speed", "filament_ramming_volumetric_speed_nc", "filament_retract_before_wipe",
    "filament_retract_length_nc", "filament_retract_restart_extra", "filament_retract_when_changing_layer",
    "filament_retraction_distances_when_cut", "filament_retraction_length", "filament_retraction_minimum_travel",
    "filament_retraction_speed", "filament_wipe", "filament_wipe_distance", "filament_z_hop",
    "filament_z_hop_types", "long_retractions_when_ec", "nozzle_temperature", "nozzle_temperature_initial_layer",
    "override_process_overhang_speed", "retraction_distances_when_ec", "slow_down_min_speed",
    "volumetric_speed_coefficients",
}


def _load_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        text = fh.read()
    cut = text.rfind("\n# MD5")
    if cut > 0:
        text = text[:cut]
    return json.loads(text)


def _first(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _family(ftype):
    m = re.match(r"[A-Z]+", str(ftype or "").upper())
    return m.group(0) if m else ""


def _bed_rect(area):
    pts = []
    for p in area or []:
        try:
            x, y = str(p).split("x")
            pts.append((float(x), float(y)))
        except ValueError:
            continue
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def _program_dirs():
    out = []
    for var in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        d = os.environ.get(var)
        if d and d not in out:
            out.append(d)
    if os.environ.get("LOCALAPPDATA"):
        out.append(os.path.join(os.environ["LOCALAPPDATA"], "Programs"))
    return out


def discover(appdata=None):
    """Slicers with a profile library on this PC: [{"id","label","data","system","app","exe","version"}]."""
    appdata = appdata or os.environ.get("APPDATA") or ""
    found, seen = [], set()
    known = {k[2].lower(): k for k in KNOWN_SLICERS}
    candidates = [k[2] for k in KNOWN_SLICERS]
    try:
        candidates += sorted(os.listdir(appdata))
    except OSError:
        pass
    for folder in candidates:
        if folder.lower() in seen:
            continue
        system = os.path.join(appdata, folder, "system")
        if not os.path.isdir(system):
            continue
        has_vendor = False
        for idx in glob.glob(os.path.join(system, "*.json")):
            vendor_dir = os.path.splitext(idx)[0]
            if os.path.isdir(os.path.join(vendor_dir, "machine")):
                has_vendor = True
                break
        if not has_vendor:
            continue
        seen.add(folder.lower())
        k = known.get(folder.lower())
        sid, label, app = (k[0], k[1], k[3]) if k else (folder.lower(), folder, folder)
        exe = None
        if k:
            for base in _program_dirs():
                cand = os.path.join(base, k[4])
                if os.path.isfile(cand):
                    exe = cand
                    break
        found.append({"id": sid, "label": label, "data": os.path.join(appdata, folder), "system": system,
                      "app": app, "exe": exe, "version": _app_version(os.path.join(appdata, folder), folder)})
    return found


def _app_version(data_dir, folder):
    conf = os.path.join(data_dir, folder + ".conf")
    try:
        with open(conf, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read(400000)
    except OSError:
        return ""
    m = re.search(r'"version"\s*:\s*"(\d+(?:\.\d+){1,3})"', text)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------- condition evaluator

_TOKEN = re.compile(r'\s*(?:(?P<num>-?\d+(?:\.\d+)?)|(?P<str>"(?:[^"\\]|\\.)*")|(?P<re>/(?:[^/\\]|\\.)*/)'
                    r'|(?P<op>==|!=|<=|>=|=~|!~|<|>|\(|\)|\[|\])|(?P<id>[A-Za-z_][A-Za-z0-9_]*))')


def eval_condition(expr, config):
    """Evaluate a PrusaSlicer-style compatible_printers_condition against a printer config.

    Supports the forms used in profile libraries: comparisons, regex match (=~ /.../),
    indexing (nozzle_diameter[0]), and/or/not and parentheses. Unknown syntax -> True.
    """
    tokens = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN.match(expr, pos)
        if not m or m.end() == pos:
            if expr[pos:].strip():
                return True
            break
        pos = m.end()
        kind = m.lastgroup
        tokens.append((kind, m.group(kind)))
    i = [0]

    def peek():
        return tokens[i[0]] if i[0] < len(tokens) else (None, None)

    def take():
        t = peek()
        i[0] += 1
        return t

    def value():
        kind, tok = take()
        if kind == "num":
            return float(tok)
        if kind == "str":
            return tok[1:-1]
        if kind == "id":
            if tok in ("true", "false"):
                return tok == "true"
            v = config.get(tok)
            if peek() == ("op", "["):
                take()
                _, idx = take()
                take()
                lst = v if isinstance(v, list) else [v]
                try:
                    v = lst[int(float(idx))]
                except (IndexError, ValueError):
                    v = None
            else:
                v = _first(v) if isinstance(v, list) else v
            return v
        if (kind, tok) == ("op", "("):
            r = expr_or()
            take()
            return r
        raise ValueError("syntax")

    def compare():
        left = value()
        kind, tok = peek()
        if kind == "op" and tok in ("==", "!=", "<", ">", "<=", ">=", "=~", "!~"):
            take()
            if tok in ("=~", "!~"):
                rk, rt = take()
                pat = rt[1:-1] if rk == "re" else str(rt)
                ok = re.search(pat, str(left if left is not None else "")) is not None
                return ok if tok == "=~" else not ok
            right = value()
            ln, rn = num(left), num(right)
            if ln is not None and rn is not None and not isinstance(left, bool):
                a, b = ln, rn
            else:
                a, b = str(left), str(right)
            return {"==": a == b, "!=": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[tok]
        return bool(left)

    def unary():
        if peek() == ("id", "not"):
            take()
            return not unary()
        return compare()

    def expr_and():
        r = unary()
        while peek() == ("id", "and"):
            take()
            r = unary() and r
        return r

    def expr_or():
        r = expr_and()
        while peek() == ("id", "or"):
            take()
            r = expr_and() or r
        return r

    try:
        return bool(expr_or())
    except Exception:
        return True


# ---------------------------------------------------------------------- library

def _merge(parent, child):
    out = dict(parent)
    for k, v in child.items():
        pv = out.get(k)
        if isinstance(v, list) and "nil" in v and isinstance(pv, list):
            # user presets: "nil" = keep the inherited value for that extruder/variant
            merged = list(pv) + [pv[-1] if pv else ""] * max(0, len(v) - len(pv))
            for j, item in enumerate(v):
                if item != "nil":
                    merged[j] = item
            out[k] = merged[:max(len(v), len(pv))]
        else:
            out[k] = v
    return out


META_FIELDS = ("inherits", "instantiation", "compatible_printers", "compatible_printers_condition",
               "filament_type", "filament_vendor", "layer_height", "name")


class Library:
    """Profiles of one slicer. Light facts of every profile file are cached on disk (keyed by
    file size and time), because opening thousands of small files is slow on Windows."""

    def __init__(self, slicer, cache_dir=None):
        self.slicer = slicer
        self.index = {}          # name -> [entry]
        self._raw = {}
        self._resolved = {}
        self._enabled = {"models": [], "filaments": set()}
        self._cache_path = os.path.join(cache_dir, "profiles-%s.json" % slicer["id"]) if cache_dir else None
        self._meta = {}
        self._meta_dirty = False
        if self._cache_path:
            try:
                self._meta = _load_json(self._cache_path)
            except (OSError, ValueError):
                self._meta = {}
        self._scan()

    def save_cache(self):
        if not self._cache_path or not self._meta_dirty:
            return
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            tmp = self._cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._meta, fh, ensure_ascii=False)
            os.replace(tmp, self._cache_path)
            self._meta_dirty = False
        except OSError:
            pass

    def meta(self, entry):
        """Light facts of one profile file (inherits, compatibility, material...)."""
        path = entry["path"]
        try:
            st = os.stat(path)
        except OSError:
            return {}
        stamp = [int(st.st_mtime), st.st_size]
        hit = self._meta.get(path)
        if hit and hit.get("t") == stamp:
            return hit["d"]
        try:
            data = self._raw.get(path) or _load_json(path)
        except (OSError, ValueError):
            data = {}
        d = {k: data[k] for k in META_FIELDS if k in data}
        self._meta[path] = {"t": stamp, "d": d}
        self._meta_dirty = True
        return d

    def meta_chain(self, name, kind, vendor=None, _depth=0):
        """Light facts merged over the inheritance chain."""
        e = self._entry(name, kind, vendor)
        if e is None or _depth > 12:
            return None
        own = self.meta(e)
        parent = own.get("inherits")
        base = self.meta_chain(parent, kind, e["vendor"] or vendor, _depth + 1) if parent else None
        out = dict(base or {})
        out.update(own)
        out["name"] = own.get("name") or name
        out["_user"] = e["user"]
        out["_vendor"] = e["vendor"] or vendor
        out["_own_instantiation"] = own.get("instantiation")
        return out

    def _add(self, name, entry):
        self.index.setdefault(name, []).append(entry)

    def _scan(self):
        system = self.slicer["system"]
        kinds = (("machine_model_list", "machine_model"), ("machine_list", "machine"),
                 ("process_list", "process"), ("filament_list", "filament"))
        for idx in sorted(glob.glob(os.path.join(system, "*.json"))):
            vendor = os.path.splitext(os.path.basename(idx))[0]
            try:
                data = _load_json(idx)
            except (OSError, ValueError):
                continue
            for list_name, kind in kinds:
                for e in data.get(list_name, []) or []:
                    if e.get("name") and e.get("sub_path"):
                        self._add(e["name"], {"vendor": vendor, "kind": kind, "user": False,
                                              "path": os.path.join(system, vendor, e["sub_path"])})
        for kind in ("machine", "process", "filament"):
            for path in glob.glob(os.path.join(self.slicer["data"], "user", "*", kind, "*.json")):
                name = os.path.splitext(os.path.basename(path))[0]
                self._add(name, {"vendor": None, "kind": kind, "user": True, "path": path})
        conf = os.path.join(self.slicer["data"], os.path.basename(self.slicer["data"]) + ".conf")
        try:
            data = _load_json(conf)
            self._enabled["models"] = data.get("models") or []
            self._enabled["filaments"] = set(data.get("filaments") or [])
        except (OSError, ValueError):
            pass

    def _entry(self, name, kind=None, vendor=None):
        entries = self.index.get(name) or []
        best = None
        for e in entries:
            score = (0 if kind is None or e["kind"] == kind else 2) + (0 if vendor and e["vendor"] == vendor else 1)
            if best is None or score < best[0]:
                best = (score, e)
        return best[1] if best else None

    def raw(self, name, kind=None, vendor=None):
        e = self._entry(name, kind, vendor)
        if e is None:
            return None, None
        if e["path"] not in self._raw:
            try:
                self._raw[e["path"]] = _load_json(e["path"])
            except (OSError, ValueError):
                self._raw[e["path"]] = {}
        return self._raw[e["path"]], e

    def resolve(self, name, kind=None, vendor=None, _depth=0):
        key = (name, kind, vendor)
        if key in self._resolved:
            return self._resolved[key]
        data, e = self.raw(name, kind, vendor)
        if data is None or _depth > 12:
            return None
        parent_name = data.get("inherits")
        own_vendor = e["vendor"] or vendor
        base = {}
        if parent_name:
            base = self.resolve(parent_name, kind, own_vendor, _depth + 1) or {}
        out = _merge(base, data)
        out["name"] = data.get("name") or name
        out["_vendor"] = own_vendor
        out["_user"] = e["user"]
        out["_inherits"] = parent_name or ""
        self._resolved[key] = out
        return out

    # ------------------------------------------------------------ printers
    def printers(self, installed_only=True):
        out = []
        models = self._enabled["models"]
        for name, entries in self.index.items():
            for e in entries:
                if e["kind"] != "machine":
                    continue
                data, _ = self.raw(name, "machine", e["vendor"])
                if not data or (not e["user"] and str(data.get("instantiation", "true")) != "true"):
                    continue
                m = self.resolve(name, "machine", e["vendor"])
                if not m:
                    continue
                model = m.get("printer_model") or ""
                nozzle = _first(m.get("nozzle_diameter")) or ""
                if installed_only and models and not e["user"]:
                    ok = any(md.get("model") == model and
                             str(nozzle) in str(md.get("nozzle_diameter", "")).split(";") for md in models)
                    if not ok:
                        continue
                out.append({"id": "%s|%s" % (self.slicer["id"], name), "slicer": self.slicer["id"],
                            "slicer_label": self.slicer["label"], "name": name, "model": model,
                            "vendor": m.get("_vendor") or "", "nozzle": str(nozzle),
                            "extruders": len(m.get("nozzle_diameter") or [1]),
                            "bed": _bed_rect(m.get("printable_area")),
                            "height": num(m.get("printable_height"), 0) or 0, "user": e["user"]})
                break
        out.sort(key=lambda p: (p["user"], p["model"].lower(), num(p["nozzle"], 0) or 0, p["name"].lower()))
        return out

    def machine(self, name):
        return self.resolve(name, "machine")

    def compatible(self, preset, machine_name, machine):
        cp = preset.get("compatible_printers") or []
        if isinstance(cp, str):
            cp = [cp] if cp else []
        if cp:
            return machine_name in cp
        cond = preset.get("compatible_printers_condition") or ""
        if isinstance(cond, list):
            cond = cond[0] if cond else ""
        if not str(cond).strip():
            return True
        return eval_condition(str(cond), machine)

    def _presets(self, kind, machine_name):
        """Profiles of `kind` usable with this printer, as light dicts (see META_FIELDS)."""
        machine = self.machine(machine_name) or {}
        out = []
        for name, entries in self.index.items():
            e = next((x for x in entries if x["kind"] == kind), None)
            if e is None:
                continue
            own = self.meta(e)
            if not e["user"] and str(own.get("instantiation", "true")) != "true":
                continue
            cp = own.get("compatible_printers")
            if cp and machine_name not in cp:
                continue
            p = self.meta_chain(name, kind, e["vendor"])
            if p and self.compatible(p, machine_name, machine):
                out.append(p)
        self.save_cache()
        return out

    def processes(self, machine_name):
        return self._presets("process", machine_name)

    def filaments(self, machine_name):
        return self._presets("filament", machine_name)

    def pick_process(self, machine_name, layer_height=None):
        machine = self.machine(machine_name) or {}
        default = machine.get("default_print_profile") or ""
        best = None
        for p in self.processes(machine_name):
            if p.get("_user"):
                continue
            lh = num(p.get("layer_height"), 0.2) or 0.2
            score = abs(lh - (layer_height or num(_first(machine.get("nozzle_diameter")), 0.4) * 0.5)) * 100
            name = p["name"]
            score += 0 if "Standard" in name else (0.3 if ("Balanced" in name or "Optimal" in name) else 0.8)
            if name == default:
                score -= 0.5
            if best is None or score < best[0]:
                best = (score, name)
        return best[1] if best else default

    def pick_filament(self, machine_name, ftype, vendor="", name="", candidates=None):
        """Closest filament profile for this printer: same material, then same product, vendor, Generic."""
        ftype = (ftype or "PLA").upper()
        family = _family(ftype)
        base = re.sub(r"\s*@.*$", "", name or "").strip().lower()
        best = None
        for p in candidates if candidates is not None else self.filaments(machine_name):
            ptype = str(_first(p.get("filament_type")) or "").upper()
            if ptype != ftype and _family(ptype) != family:
                continue
            pname = p["name"]
            pbase = re.sub(r"\s*@.*$", "", pname).strip().lower()
            pvendor = str(_first(p.get("filament_vendor")) or "")
            score = 3.0
            if base and pbase == base:
                score = 0.0
            elif vendor and pvendor.lower() == str(vendor).lower():
                score = 1.0
            elif pvendor.lower() == "generic" or pbase.startswith("generic"):
                score = 2.0
            if ptype != ftype:
                score += 4.0          # same family only (PA -> PA6-CF)
            if p.get("_user"):
                score += 0.4
            if pname in self._enabled["filaments"]:
                score -= 0.2
            if best is None or score < best[0]:
                best = (score, pname)
        if best:
            return best[1]
        machine = self.machine(machine_name) or {}
        default = _first(machine.get("default_filament_profile"))
        return default or ""

    # ------------------------------------------------------------ building a project config
    @staticmethod
    def _fill_filament_keys(cfg, source, n):
        _fill_filament_keys_impl(cfg, source or {}, n)

    def build_config(self, machine_name, process_name, filament_names, source=None, colours=None):
        """Complete flat project config for a single-nozzle printer, the way the slicer stores it."""
        machine = self.machine(machine_name)
        process = self.resolve(process_name, "process")
        fils = [self.resolve(n, "filament") for n in filament_names]
        if not machine or not process or not all(fils):
            missing = [n for n, f in zip(filament_names, fils) if not f]
            raise KeyError(", ".join(missing) or (process_name if not process else machine_name))
        n = len(fils)
        source = source or {}
        cfg = {}
        for k, v in process.items():
            if k not in META_KEYS and not k.startswith("_"):
                cfg[k] = v
        fkeys = []
        for f in fils:
            for k in f:
                if k not in META_KEYS and not k.startswith("_") and k not in fkeys:
                    fkeys.append(k)
        # single-nozzle target: one value per filament for per-variant keys, taken for this printer's variant
        etype = str(_first(machine.get("extruder_type")) or "Direct Drive")
        volume = str(_first(machine.get("default_nozzle_volume_type")) or "Standard")
        variant = "%s %s" % (etype, volume)

        def pick(f, v):
            fev = f.get("filament_extruder_variant")
            fev = fev if isinstance(fev, list) else []
            j = fev.index(variant) if variant in fev else 0
            return v[j] if j < len(v) else v[0]

        for k in fkeys:
            vals = []
            if k in source:
                as_list = isinstance(source.get(k), list)
            else:
                as_list = any(isinstance(f.get(k), list) for f in fils)
            filler = next((f[k] for f in fils if k in f), "")
            for f in fils:
                v = f.get(k, filler)
                if isinstance(v, list) and v and k in VARIANT_FILAMENT_KEYS:
                    vals.append(pick(f, v))
                else:
                    vals.extend(v if isinstance(v, list) else [v])
            cfg[k] = vals if as_list else (vals[0] if vals else "")
        for k, v in machine.items():
            if k not in META_KEYS and not k.startswith("_"):
                cfg[k] = v
        self._fill_filament_keys(cfg, source, n)
        variants = [variant] * n
        owners = [str(i + 1) for i in range(n)]
        cfg["filament_extruder_variant"] = variants
        cfg["filament_self_index"] = owners
        cfg["print_settings_id"] = process["name"]
        cfg["printer_settings_id"] = machine["name"]
        cfg["filament_settings_id"] = [f["name"] for f in fils]
        cfg["filament_ids"] = [str(f.get("filament_id") or "") for f in fils]
        cfg["inherits_group"] = ([process["_inherits"] if process.get("_user") else ""] +
                                 [f["_inherits"] if f.get("_user") else "" for f in fils] +
                                 [machine["_inherits"] if machine.get("_user") else ""])
        cfg["different_settings_to_system"] = [""] * (n + 2)
        cfg["from"] = "project"
        cfg["name"] = "project_settings"
        cfg["version"] = self.slicer.get("version") or str(source.get("version") or "")
        default_colours = [str(_first(f.get("default_filament_colour")) or "#FFFFFF") or "#FFFFFF" for f in fils]
        colours = list(colours or [])
        cfg["filament_colour"] = [colours[i] if i < len(colours) and colours[i] else default_colours[i]
                                  for i in range(n)]
        cfg["filament_map"] = ["1"] * n
        cfg["filament_map_mode"] = str(source.get("filament_map_mode") or "Auto For Flush")
        bed = str(source.get("curr_bed_type") or "")
        if bed not in BED_TEMP_KEYS or BED_TEMP_KEYS[bed][0] not in cfg:
            bed = str(machine.get("default_bed_type") or "")
            if bed not in BED_TEMP_KEYS:
                bed = "Textured PEI Plate" if "textured_plate_temp" in cfg else "Cool Plate"
        cfg["curr_bed_type"] = bed
        src_matrix = source.get("flush_volumes_matrix")
        if isinstance(src_matrix, list) and len(src_matrix) == n * n:
            cfg["flush_volumes_matrix"] = list(src_matrix)
        else:
            cfg["flush_volumes_matrix"] = ["0" if r == c else "280" for r in range(n) for c in range(n)]
        cfg["flush_volumes_vector"] = ["140"] * (2 * n)
        cfg["flush_multiplier"] = ["1"]
        rect = _bed_rect(machine.get("printable_area")) or [0, 0, 200, 200]
        wx = num(_first(source.get("wipe_tower_x")), None)
        wy = num(_first(source.get("wipe_tower_y")), None)
        if wx is None or not (rect[0] + 10 <= wx <= rect[2] - 70):
            wx = rect[0] + (rect[2] - rect[0]) * 0.65
        if wy is None or not (rect[1] + 10 <= wy <= rect[3] - 70):
            wy = rect[1] + (rect[3] - rect[1]) * 0.7
        cfg["wipe_tower_x"] = ["%.3f" % wx]
        cfg["wipe_tower_y"] = ["%.3f" % wy]
        return cfg


def _fill_filament_keys_impl(cfg, source, n):
    """Per-filament settings the target profiles do not define, taken from the source project.

    A slicer fills a missing key with its built-in default, which holds one value; with several
    filaments that breaks slicing (seen with filament_shrink in QIDI Studio 2.7). Only keys shaped
    "one value per filament" (or per filament and variant, collapsed) are copied.
    """
    names = source.get("filament_settings_id")
    src_n = len(names) if isinstance(names, list) else 1
    owners = source.get("filament_self_index") if isinstance(source.get("filament_self_index"), list) else []
    if src_n != n:
        return
    for k, v in source.items():
        if k in cfg or k in META_KEYS or not isinstance(v, list) or not v:
            continue
        if len(v) == n:
            cfg[k] = list(v)
        elif owners and len(v) == len(owners) and len(owners) > n:
            seen, out = set(), []
            for o, x in zip(owners, v):
                if o not in seen:
                    seen.add(o)
                    out.append(x)
            if len(out) == n:
                cfg[k] = out


def libraries(appdata=None):
    return [Library(s) for s in discover(appdata)]
