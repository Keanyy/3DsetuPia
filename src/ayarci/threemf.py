"""3DsetuPia - 3MF projects of Bambu Studio, QIDI Studio, OrcaSlicer and their relatives.

Reading: settings (Metadata/project_settings.config), objects, parts, plates and
meshes (only to measure them locally). Writing: a new file in which only the
entries 3DsetuPia is responsible for change; meshes, painting, colours and
per-object settings are copied byte for byte.
"""

import io
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET

import numpy as np

from .catalog import SETTINGS  # bundle:strip

SETTINGS_ENTRY = "Metadata/project_settings.config"
MODEL_ENTRY = "3D/3dmodel.model"
MODEL_SETTINGS_ENTRY = "Metadata/model_settings.config"
SLICE_INFO_ENTRY = "Metadata/slice_info.config"

_ATTR = re.compile(r'([\w:]+)\s*=\s*"([^"]*)"')
_OBJECT = re.compile(r"<(?:\w+:)?object\b([^>]*)>(.*?)</(?:\w+:)?object>", re.S)
_VERTEX = re.compile(r'<(?:\w+:)?vertex\b([^>]*)/?>')
_TRIANGLE = re.compile(r'<(?:\w+:)?triangle\b([^>]*)/?>')
_COMPONENT = re.compile(r'<(?:\w+:)?component\b([^>]*)/?>')
_ITEM = re.compile(r'<(?:\w+:)?item\b[^>]*?/?>')
_FAST_VERTEX = re.compile(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"')
_FAST_TRIANGLE = re.compile(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"')
_PAINT = re.compile(r'\b(?:paint_color|slic3rpe:mmu_segmentation|mmu_segmentation)="')

FLAVORS = (("BambuStudio", "bambu", "Bambu Studio"), ("QIDIStudio", "qidi", "QIDI Studio"),
           ("OrcaSlicer", "orca", "OrcaSlicer"), ("Snapmaker", "orca", "Snapmaker Orca"),
           ("ElegooSlicer", "orca", "Elegoo Slicer"), ("CrealityPrint", "orca", "Creality Print"),
           ("AnycubicSlicer", "bambu", "Anycubic Slicer Next"))


class ProjectError(Exception):
    def __init__(self, code, detail=""):
        super().__init__(code if not detail else "%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _attrs(text):
    return {k.split(":")[-1] if k.startswith("p:") else k: v for k, v in _ATTR.findall(text)}


def parse_transform(text):
    """3MF 'm00 m01 m02 m10 ... m32' (row vectors) -> 4x4 matrix for column vectors."""
    if not text:
        return np.eye(4)
    vals = [float(x) for x in text.split()]
    if len(vals) != 12:
        return np.eye(4)
    m = np.eye(4)
    m[:3, :3] = np.array(vals[:9]).reshape(3, 3).T
    m[:3, 3] = vals[9:12]
    return m


def format_transform(m):
    r = np.asarray(m, dtype=np.float64)
    vals = list(r[:3, :3].T.reshape(-1)) + list(r[:3, 3])
    return " ".join(("%.9g" % v) if abs(v) > 1e-12 else "0" for v in vals)


def app_flavor(app):
    for prefix, flavor, label in FLAVORS:
        if (app or "").startswith(prefix):
            return flavor, label
    return "other", (app or "").split("-")[0] or "?"


def _floats(attr_list, names):
    return [[float(a.get(n, 0.0)) for n in names] for a in attr_list]


def _parse_mesh(body):
    """Vertices (N,3) float32 and triangles (M,3) int32 of one <mesh>; quick path for common writers."""
    nv = body.count("<vertex ") + body.count(":vertex ")
    fast_v = _FAST_VERTEX.findall(body)
    if fast_v and len(fast_v) == nv:
        v = np.array(fast_v, dtype=np.float64)
    else:
        v = np.array(_floats([_attrs(a) for a in _VERTEX.findall(body)], ("x", "y", "z")), dtype=np.float64)
    nt = body.count("<triangle ") + body.count(":triangle ")
    fast_t = _FAST_TRIANGLE.findall(body)
    if fast_t and len(fast_t) == nt:
        t = np.array(fast_t, dtype=np.int64)
    else:
        t = np.array([[int(a.get("v1", 0)), int(a.get("v2", 0)), int(a.get("v3", 0))]
                      for a in (_attrs(x) for x in _TRIANGLE.findall(body))], dtype=np.int64)
    if v.size == 0:
        v = np.zeros((0, 3))
    if t.size == 0:
        t = np.zeros((0, 3), dtype=np.int64)
    return v.astype(np.float32), t.astype(np.int32), bool(_PAINT.search(body))


class Project:
    """An opened 3MF (or a mesh file wrapped as one, see meshfiles.py)."""

    def __init__(self, path=None):
        self.path = path
        self.kind = "project"          # "project" (has settings), "model" (geometry only)
        self.entries = []              # [(ZipInfo, bytes)] in original order
        self.app = ""
        self.flavor = "other"
        self.app_label = ""
        self.settings = None           # dict from project_settings.config
        self._settings_crlf = False
        self.objects = []              # see _read_objects
        self.items = []                # build items: {"objectid","index","transform","printable","plate","attrs"}
        self.plates = []               # [{"id": int, "instances": [(objid, inst)], ...}]
        self.sliced = False
        self._resources = {}           # (file, objectid) -> {"mesh": (v, t, painted)} | {"components": [...]}

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, path):
        p = cls(path)
        try:
            zf = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError) as exc:
            raise ProjectError("bad_file", str(exc))
        with zf:
            for info in zf.infolist():
                p.entries.append((info, zf.read(info.filename)))
        p._index()
        return p

    def entry(self, name):
        for info, data in self.entries:
            if info.filename == name:
                return data
        return None

    def names(self):
        return [info.filename for info, _ in self.entries]

    def _index(self):
        model = self.entry(MODEL_ENTRY)
        if model is None:
            # some writers use another file name for the root model; follow _rels/.rels
            rels = (self.entry("_rels/.rels") or b"").decode("utf-8", "replace")
            m = re.search(r'Target="/?([^"]+\.model)"', rels)
            if m:
                model = self.entry(m.group(1))
                self._root = m.group(1)
            if model is None:
                raise ProjectError("no_model")
        else:
            self._root = MODEL_ENTRY
        text = model.decode("utf-8", "replace")
        m = re.search(r'<metadata name="Application">([^<]*)</metadata>', text)
        self.app = m.group(1).strip() if m else ""
        self.flavor, self.app_label = app_flavor(self.app)
        raw = self.entry(SETTINGS_ENTRY)
        if raw is not None:
            try:
                s = raw.decode("utf-8-sig")
                self.settings = json.loads(s)
                self._settings_crlf = "\r\n" in s[:200]
            except ValueError as exc:
                raise ProjectError("bad_settings", str(exc))
        self.kind = "project" if isinstance(self.settings, dict) else "model"
        self.sliced = any(re.match(r"Metadata/plate_\d+\.gcode$", n) for n in self.names())
        self._read_resources(self._root, text)
        self._read_build(text)
        self._read_model_settings()

    def _read_resources(self, fname, text):
        for attrs_text, body in _OBJECT.findall(text):
            a = _attrs(attrs_text)
            oid = a.get("id")
            if oid is None:
                continue
            comps = []
            for ctext in _COMPONENT.findall(body):
                ca = _attrs(ctext)
                path = ca.get("path", "").lstrip("/") or fname
                comps.append({"file": path, "objectid": ca.get("objectid"),
                              "transform": parse_transform(ca.get("transform"))})
            res = {"type": a.get("type", "model"), "components": comps, "body": None}
            if not comps and "mesh>" in body:
                res["body"] = body
            self._resources[(fname, oid)] = res
            if comps:
                for c in comps:
                    if c["file"] != fname and not any(k[0] == c["file"] for k in self._resources):
                        data = self.entry(c["file"])
                        if data is not None:
                            self._read_resources(c["file"], data.decode("utf-8", "replace"))

    def _read_build(self, text):
        build = re.search(r"<(?:\w+:)?build\b[^>]*>(.*?)</(?:\w+:)?build>", text, re.S)
        if not build:
            return
        counts = {}
        for raw in _ITEM.findall(build.group(1)):
            a = _attrs(raw)
            oid = a.get("objectid")
            idx = counts.get(oid, 0)
            counts[oid] = idx + 1
            self.items.append({"objectid": oid, "index": idx, "transform": parse_transform(a.get("transform")),
                               "printable": a.get("printable", "1") != "0", "plate": 1, "raw": raw})

    def _read_model_settings(self):
        """Object names, filament (extruder) assignments, per-object settings, plates."""
        raw = self.entry(MODEL_SETTINGS_ENTRY)
        by_id = {}
        if raw is not None:
            try:
                root = ET.fromstring(raw.decode("utf-8", "replace"))
            except ET.ParseError:
                root = None
            if root is not None:
                for obj in root.findall("object"):
                    meta = {m.get("key"): m.get("value") for m in obj.findall("metadata") if m.get("key")}
                    faces = 0
                    for m in obj.findall("metadata"):
                        if m.get("face_count"):
                            faces = int(m.get("face_count") or 0)
                    parts = []
                    for part in obj.findall("part"):
                        pm = {m.get("key"): m.get("value") for m in part.findall("metadata") if m.get("key")}
                        parts.append({"id": part.get("id"), "subtype": part.get("subtype", "normal_part"),
                                      "extruder": pm.get("extruder"), "name": pm.get("name", ""),
                                      "overrides": [k for k in pm if k in SETTINGS]})
                    by_id[obj.get("id")] = {"name": meta.get("name", ""), "extruder": meta.get("extruder"),
                                            "faces": faces, "parts": parts,
                                            "overrides": [k for k in meta if k in SETTINGS]}
                for plate in root.findall("plate"):
                    pm = {m.get("key"): m.get("value") for m in plate.findall("metadata") if m.get("key")}
                    inst = []
                    for mi in plate.findall("model_instance"):
                        im = {m.get("key"): m.get("value") for m in mi.findall("metadata") if m.get("key")}
                        inst.append((im.get("object_id"), int(im.get("instance_id") or 0)))
                    try:
                        pid = int(pm.get("plater_id") or len(self.plates) + 1)
                    except ValueError:
                        pid = len(self.plates) + 1
                    self.plates.append({"id": pid, "name": pm.get("plater_name", ""), "instances": inst,
                                        "meta": pm})
        if not self.plates:
            self.plates = [{"id": 1, "name": "", "instances": [], "meta": {}}]
        plate_of = {}
        for pl in self.plates:
            for key in pl["instances"]:
                plate_of[key] = pl["id"]
        for it in self.items:
            it["plate"] = plate_of.get((it["objectid"], it["index"]), self.plates[0]["id"])
        seen = {}
        self.objects = []
        for oid in dict.fromkeys(it["objectid"] for it in self.items):
            info = by_id.get(oid, {})
            name = info.get("name") or "Nesne %s" % oid
            if name in seen:
                seen[name] += 1
                name = "%s #%d" % (name, seen[name])
            else:
                seen[name] = 1
            insts = [it for it in self.items if it["objectid"] == oid]
            self.objects.append({"id": oid, "name": name, "extruder": info.get("extruder"),
                                 "faces": info.get("faces", 0), "parts": info.get("parts", []),
                                 "overrides": sorted(set(info.get("overrides", []) +
                                                         [k for p in info.get("parts", []) for k in p["overrides"]])),
                                 "instances": len([i for i in insts if i["printable"]]),
                                 "painted": False, "size_mm": None})

    # ------------------------------------------------------------------ meshes
    def _mesh_parts(self, fname, oid, matrix, depth=0):
        res = self._resources.get((fname, oid))
        if res is None or depth > 8:
            return []
        if res["body"] is not None:
            if "parsed" not in res:
                res["parsed"] = _parse_mesh(res["body"])
                res["body"] = None
            v, t, painted = res["parsed"]
            return [{"vertices": v, "triangles": t, "matrix": matrix, "painted": painted,
                     "component": oid, "type": res["type"]}]
        if "parsed" in res:
            v, t, painted = res["parsed"]
            return [{"vertices": v, "triangles": t, "matrix": matrix, "painted": painted,
                     "component": oid, "type": res["type"]}]
        out = []
        for c in res["components"]:
            for part in self._mesh_parts(c["file"], c["objectid"], matrix @ c["transform"], depth + 1):
                if depth == 0:
                    part["component"] = c["objectid"]
                out.append(part)
        return out

    def object_parts(self, obj, item=None):
        """World-space model parts of one object instance (modifiers, blockers and negative parts skipped)."""
        if item is None:
            item = next((it for it in self.items if it["objectid"] == obj["id"]), None)
        if item is None:
            return []
        subtype = {str(p["id"]): p["subtype"] for p in obj.get("parts", [])}
        out = []
        for part in self._mesh_parts(self._root, obj["id"], item["transform"]):
            if subtype.get(str(part["component"]), "normal_part") != "normal_part":
                continue
            if part["type"] not in ("model", "solidsupport", ""):
                continue
            out.append(part)
        return out

    def measure_parts(self):
        """Parts in the format geometry.analyze_plate() expects (first printable instance of each object)."""
        parts = []
        for obj in self.objects:
            item = next((it for it in self.items if it["objectid"] == obj["id"] and it["printable"]), None)
            if item is None:
                continue
            ps = self.object_parts(obj, item)
            obj["painted"] = any(p["painted"] for p in ps)
            for p in ps:
                parts.append({"object": obj["name"], "vertices": p["vertices"], "triangles": p["triangles"],
                              "matrix": p["matrix"]})
        return parts

    def item_bounds(self, item):
        """World bounding box (min xyz, max xyz) of one build item, or None."""
        obj = next((o for o in self.objects if o["id"] == item["objectid"]), None)
        if obj is None:
            return None
        lo, hi = None, None
        for p in self.object_parts(obj, item):
            v = np.asarray(p["vertices"], dtype=np.float64)
            if not len(v):
                continue
            m = np.asarray(p["matrix"])
            w = v @ m[:3, :3].T + m[:3, 3]
            a, b = w.min(axis=0), w.max(axis=0)
            lo = a if lo is None else np.minimum(lo, a)
            hi = b if hi is None else np.maximum(hi, b)
        if lo is None:
            return None
        return lo, hi

    # ------------------------------------------------------------------ facts for the UI and the engine
    def filament_weights(self):
        """Faces printed with each filament slot (1-based), from object/part assignments."""
        weights = {}
        for obj in self.objects:
            ext = obj.get("extruder") or "1"
            parts = [p for p in obj.get("parts", []) if p["subtype"] == "normal_part"]
            if parts and any(p.get("extruder") for p in parts):
                share = max(1, obj.get("faces", 1)) / len(parts)
                for p in parts:
                    e = p.get("extruder") or ext
                    weights[e] = weights.get(e, 0) + share
            else:
                weights[ext] = weights.get(ext, 0) + max(1, obj.get("faces", 1)) * max(1, obj["instances"])
        out = {}
        for k, v in weights.items():
            try:
                out[int(k)] = out.get(int(k), 0) + v
            except (TypeError, ValueError):
                out[1] = out.get(1, 0) + v
        return out

    def main_filament(self):
        w = self.filament_weights()
        return max(w, key=w.get) if w else 1

    def used_filaments(self):
        return sorted(self.filament_weights())

    def plate_filament_map(self):
        """Filament -> extruder map stored on the plate of the main object (multi-nozzle printers)."""
        main = str(self.main_filament())
        plate_id = None
        for obj in self.objects:
            if str(obj.get("extruder") or "1") == main:
                plate_id = next((it["plate"] for it in self.items if it["objectid"] == obj["id"]), None)
                break
        for pl in self.plates:
            if plate_id is None or pl["id"] == plate_id:
                raw = (pl.get("meta") or {}).get("filament_maps", "")
                if raw.strip():
                    return raw.split()
                break
        return None

    # ------------------------------------------------------------------ writing
    def settings_bytes(self, cfg):
        text = json.dumps(cfg, ensure_ascii=False, indent=4, sort_keys=True)
        if self._settings_crlf:
            text = text.replace("\n", "\r\n")
        return (text + ("\r\n" if self._settings_crlf else "\n")).encode("utf-8")

    def write(self, out_path, settings=None, moves=None, plate_meta=None, app=None):
        """Write a copy. settings: new config dict; moves: {item position -> 4x4}; plate_meta: {key: value};
        app: new "Application" name (the slicer the project now belongs to)."""
        replace = {}
        if settings is not None:
            replace[SETTINGS_ENTRY] = self.settings_bytes(settings)
        if moves or app:
            replace[self._root] = self._root_model(moves or {}, app)
        if plate_meta:
            raw = replace.get(MODEL_SETTINGS_ENTRY, self.entry(MODEL_SETTINGS_ENTRY))
            if raw is not None:
                replace[MODEL_SETTINGS_ENTRY] = _set_plate_meta(raw, plate_meta)
        drop = set()
        if self.sliced:
            # settings changed, so the old G-code no longer matches: hand back an unsliced project
            drop = {n for n in self.names() if re.match(r"Metadata/plate_\d+\.gcode(\.md5)?$", n)}
            info = self.entry(SLICE_INFO_ENTRY)
            if info is not None:
                replace[SLICE_INFO_ENTRY] = re.sub(rb"\s*<plate>.*?</plate>", b"", info, flags=re.S)
            ms = replace.get(MODEL_SETTINGS_ENTRY, self.entry(MODEL_SETTINGS_ENTRY))
            if ms is not None:
                replace[MODEL_SETTINGS_ENTRY] = re.sub(rb'(<metadata key="gcode_file" value=")[^"]*(")',
                                                       rb"\1\2", ms)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for info, data in self.entries:
                if info.filename in drop:
                    continue
                new = replace.get(info.filename, data)
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zf.writestr(zi, new)
        tmp = out_path + ".part"
        with open(tmp, "wb") as fh:
            fh.write(buf.getvalue())
        os.replace(tmp, out_path)
        return out_path

    def _root_model(self, moves, app=None):
        text = self.entry(self._root).decode("utf-8")
        if app:
            text = re.sub(r'(<metadata name="Application">)[^<]*(</metadata>)',
                          lambda m: m.group(1) + app + m.group(2), text, count=1)
        build = re.search(r"(<(?:\w+:)?build\b[^>]*>)(.*?)(</(?:\w+:)?build>)", text, re.S)
        if not build:
            return text.encode("utf-8")
        body = build.group(2)
        pos = [0]

        def sub(m):
            i = pos[0]
            pos[0] += 1
            raw = m.group(0)
            if i not in moves:
                return raw
            new_t = format_transform(moves[i])
            if re.search(r'\btransform="', raw):
                return re.sub(r'\btransform="[^"]*"', 'transform="%s"' % new_t, raw)
            return re.sub(r"\s*/?>$", lambda e: ' transform="%s"%s' % (new_t, e.group(0)), raw, count=1)

        body = _ITEM.sub(sub, body)
        return (text[:build.start(2)] + body + text[build.end(2):]).encode("utf-8")


def _set_plate_meta(raw, values):
    """Set plate-level <metadata key=... value=...> entries in model_settings.config (bytes level)."""
    out = raw
    for key, value in values.items():
        pat = re.compile(rb'(<metadata key="' + re.escape(key.encode()) + rb'" value=")[^"]*(")')
        out = pat.sub(lambda m: m.group(1) + value.encode("utf-8") + m.group(2), out)
    return out
