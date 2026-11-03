"""3DsetuPia - the desktop program's workflow, independent of any window.

open(path)  -> Job: a 3MF project (with settings), a settings-free 3MF, or an STL/OBJ.
prepare()   -> measure the model, build the target settings (same printer, or another
               printer from the installed slicers' profiles), rules/AI suggestions,
               safety filter, bed placement.
save()      -> write a new 3MF with the chosen suggestions; the source file is never changed.
"""

import copy
import os
import time

from .catalog import SETTINGS  # bundle:strip
from .geometry import analyze_plate  # bundle:strip
from .projcfg import ProjectConfig  # bundle:strip
from .threemf import Project, ProjectError  # bundle:strip
from .meshfiles import MESH_EXTENSIONS, load_meshes, meshes_from_project, build_project  # bundle:strip
from .profiles import discover, Library, _bed_rect, _first  # bundle:strip
from .placement import relocate, layout_new  # bundle:strip
from .assist import suggest  # bundle:strip
from .rules import num  # bundle:strip
from .i18n import msg  # bundle:strip

FLAVOR_OF_SLICER = {"bambu": "bambu", "qidi": "qidi", "orca": "orca", "snapmaker": "orca", "elegoo": "orca",
                    "anycubic": "bambu"}


def _flavor(project_flavor):
    return project_flavor if project_flavor in ("bambu", "qidi", "orca") else "common"


class Job:
    def __init__(self, path):
        self.path = path
        self.project = None        # Project with settings, or None
        self.meshes = None         # plain meshes when the file has no settings
        self.plan = None


class Engine:
    def __init__(self, cache_dir=None, appdata=None):
        self.cache_dir = cache_dir
        self.slicers = discover(appdata)
        self._libs = {}

    # ------------------------------------------------------------ profiles
    def library(self, slicer_id):
        if slicer_id not in self._libs:
            s = next((x for x in self.slicers if x["id"] == slicer_id), None)
            if s is None:
                return None
            self._libs[slicer_id] = Library(s, self.cache_dir)
        return self._libs[slicer_id]

    def printers(self, installed_only=True):
        out = []
        for s in self.slicers:
            lib = self.library(s["id"])
            out += lib.printers(installed_only)
        return out

    def warm_up(self, progress=None):
        """Read every installed slicer's profile index once (cached on disk for the next start)."""
        for s in self.slicers:
            lib = self.library(s["id"])
            for p in lib.printers(True):
                if p["extruders"] == 1:
                    lib.filaments(p["name"])
                    lib.processes(p["name"])
            lib.save_cache()

    def filament_choices(self, printer_id):
        slicer_id, name = printer_id.split("|", 1)
        lib = self.library(slicer_id)
        out = []
        for f in lib.filaments(name):
            out.append({"name": f["name"], "type": str(_first(f.get("filament_type")) or ""),
                        "vendor": str(_first(f.get("filament_vendor")) or ""), "user": bool(f.get("_user"))})
        out.sort(key=lambda f: (f["user"], f["type"], f["name"].lower()))
        return out

    # ------------------------------------------------------------ open
    def open(self, path):
        job = Job(path)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".3mf":
            project = Project.load(path)
            if project.kind == "project":
                job.project = project
            else:
                job.meshes = meshes_from_project(project)
        elif ext in MESH_EXTENSIONS:
            job.meshes = load_meshes(path)
        else:
            raise ProjectError("unsupported", ext)
        return job

    def describe(self, job, lang="tr"):
        """What the page shows about the opened file."""
        info = {"path": job.path, "file": os.path.basename(job.path), "has_settings": job.project is not None}
        if job.project is None:
            info.update({"kind": "model", "objects": [{"name": m["name"], "size_mm": _size(m["vertices"])}
                                                      for m in job.meshes], "plates": 1})
            return info
        p = job.project
        cfg = p.settings
        names = cfg.get("filament_settings_id")
        names = names if isinstance(names, list) else [names or ""]
        colours = cfg.get("filament_colour") if isinstance(cfg.get("filament_colour"), list) else []
        types = cfg.get("filament_type") if isinstance(cfg.get("filament_type"), list) else []
        used = p.used_filaments()
        objects = []
        for obj, it in ((o, next((i for i in p.items if i["objectid"] == o["id"]), None)) for o in p.objects):
            b = p.item_bounds(it) if it else None
            objects.append({"name": obj["name"], "instances": obj["instances"],
                            "size_mm": [round(float(x), 1) for x in (b[1] - b[0])] if b else None,
                            "overrides": obj["overrides"]})
        info.update({
            "kind": "project", "app": p.app_label, "app_version": p.app.split("-")[-1] if "-" in p.app else "",
            "printer": str(cfg.get("printer_settings_id") or ""), "printer_model": str(cfg.get("printer_model") or ""),
            "nozzle": str(_first(cfg.get("nozzle_diameter")) or ""),
            "extruders": len(cfg.get("nozzle_diameter") or [1]) if isinstance(cfg.get("nozzle_diameter"), list) else 1,
            "process": str(cfg.get("print_settings_id") or ""), "bed_type": str(cfg.get("curr_bed_type") or ""),
            "bed": _bed_rect(cfg.get("printable_area")), "plates": len(p.plates), "objects": objects,
            "sliced": p.sliced, "main_filament": p.main_filament(),
            "filaments": [{"slot": i + 1, "name": names[i] if i < len(names) else "",
                           "type": types[i] if i < len(types) else "",
                           "colour": colours[i] if i < len(colours) else "", "used": (i + 1) in used}
                          for i in range(len(names))],
        })
        info["same_printer_id"] = self._find_printer(info["printer"])
        return info

    def _find_printer(self, name):
        for s in self.slicers:
            lib = self.library(s["id"])
            if lib.machine(name):
                return "%s|%s" % (s["id"], name)
        return None

    # ------------------------------------------------------------ prepare
    def prepare(self, job, target="same", slot=None, filament=None, intent="balanced", note="", lang="tr",
                provider_cfg=None, use_ai=True, progress=None):
        t0 = time.time()
        say = progress or (lambda text: None)
        warnings, notes = [], []
        moves, plate_meta, app, placement = None, None, None, []
        if target in (None, "", "same"):
            if job.project is None:
                raise ProjectError("need_target")
            base = job.project
            cfg = copy.deepcopy(base.settings)
            flavor = _flavor(base.flavor)
            slot = int(slot or base.main_filament())
            fmap = base.plate_filament_map()
            target_label = str(cfg.get("printer_settings_id") or "")
        else:
            slicer_id, machine_name = target.split("|", 1)
            lib = self.library(slicer_id)
            if lib is None:
                raise ProjectError("profile_missing", target)
            machine = lib.machine(machine_name)
            if not machine:
                raise ProjectError("profile_missing", machine_name)
            if len(machine.get("nozzle_diameter") or [1]) > 1:
                raise ProjectError("multi_nozzle_target", machine_name)
            flavor = FLAVOR_OF_SLICER.get(slicer_id, "common")
            app = "%s-%s" % (lib.slicer["app"], lib.slicer.get("version") or "")
            dst_rect = _bed_rect(machine.get("printable_area")) or [0, 0, 200, 200]
            dst_h = num(machine.get("printable_height"), 0) or 0
            candidates = lib.filaments(machine_name)
            fmap = None
            target_label = machine_name
            if job.project is not None:
                base = job.project
                src = base.settings
                n = len(src.get("filament_settings_id")) if isinstance(src.get("filament_settings_id"), list) else 1
                slot = int(slot or base.main_filament())
                lh = num(src.get("layer_height"), 0.2)
                fil_names = []
                for i in range(n):
                    if filament and i + 1 == slot:
                        fil_names.append(filament)
                        continue
                    fil_names.append(lib.pick_filament(machine_name, _idx(src.get("filament_type"), i),
                                                       _idx(src.get("filament_vendor"), i),
                                                       _idx(src.get("filament_settings_id"), i), candidates))
                process = lib.pick_process(machine_name, lh)
                try:
                    cfg = lib.build_config(machine_name, process, fil_names, source=src,
                                           colours=src.get("filament_colour") if isinstance(
                                               src.get("filament_colour"), list) else None)
                except KeyError as exc:
                    raise ProjectError("profile_missing", str(exc))
                src_rect = _bed_rect(src.get("printable_area")) or dst_rect
                say(msg(lang, "measuring"))
                moves, placement = relocate(base, src_rect, dst_rect, dst_h)
                plate_meta = {"filament_maps": " ".join(["1"] * n), "filament_map_mode": "Auto For Flush"}
                notes.append(msg(lang, "retarget", src=str(src.get("printer_settings_id") or "?"),
                                 dst=machine_name, process=process))
                for i, (old, new) in enumerate(zip(_as_list(src.get("filament_settings_id")), fil_names)):
                    if (i + 1) in base.used_filaments() or i + 1 == slot:
                        notes.append(msg(lang, "fil_mapped", slot=i + 1, src=old, dst=new))
            else:
                slot = 1
                fil = filament or lib.pick_filament(machine_name, "PLA", "Generic", "Generic PLA", candidates)
                process = lib.pick_process(machine_name)
                try:
                    cfg = lib.build_config(machine_name, process, [fil])
                except KeyError as exc:
                    raise ProjectError("profile_missing", str(exc))
                positions, fits = layout_new(job.meshes, dst_rect)
                base = build_project(job.meshes, cfg, app, positions, job.path)
                too_tall = [m["name"] for m in job.meshes if dst_h and _size(m["vertices"])[2] > dst_h + 0.01]
                placement = [{"plate": 1, "objects": len(job.meshes), "status": "new" if fits else "new_too_big",
                              "too_big": [] if fits else [m["name"] for m in job.meshes], "too_tall": too_tall}]
                cfg = copy.deepcopy(base.settings)
                app = None   # already written by build_project
        say(msg(lang, "measuring"))
        parts = base.measure_parts()
        if not parts:
            raise ProjectError("no_model")
        pc = ProjectConfig(cfg, slot - 1, filament_map=fmap)
        ctx = pc.context(lang, intent, note)
        ctx["flavor"] = flavor
        analysis = analyze_plate(parts)
        out = suggest(analysis, ctx, provider_cfg or {"provider": "none"}, use_ai, progress=say)
        warnings += out["warnings"]
        if job.project is not None and job.project.sliced:
            warnings.append(msg(lang, "sliced_input"))
        over = [o["name"] for o in base.objects if o.get("overrides")]
        if over:
            warnings.append(msg(lang, "object_overrides", names=", ".join(over[:4])))
        if pc.filament_count > 1:
            warnings.append(msg(lang, "multi_filament_app", n=pc.filament_count, name=ctx["filament"].get("preset")))
        if any(o.get("painted") for o in base.objects):
            warnings.append(msg(lang, "painted"))
        for entry in placement:
            if entry["status"] == "moved":
                notes.append(msg(lang, "place_moved", plate=entry["plate"]))
            elif entry["status"] == "packed":
                notes.append(msg(lang, "place_packed", plate=entry["plate"]))
            elif entry["status"] == "crowded":
                warnings.append(msg(lang, "place_crowded", plate=entry["plate"]))
            elif entry["status"] == "too_big":
                warnings.append(msg(lang, "place_too_big", plate=entry["plate"], names=", ".join(entry["too_big"])))
            elif entry["status"] == "new":
                notes.append(msg(lang, "place_new"))
            elif entry["status"] == "new_too_big":
                warnings.append(msg(lang, "place_new_too_big"))
            if entry.get("too_tall"):
                warnings.append(msg(lang, "place_too_tall", names=", ".join(entry["too_tall"])))
        job.plan = {"base": base, "cfg": cfg, "slot": slot, "fmap": fmap, "changes": out["changes"],
                    "moves": moves, "plate_meta": plate_meta, "app": app, "target": target_label}
        return {"ok": True, "source": out["source"], "summary": out["summary"], "changes": out["changes"],
                "warnings": warnings, "notes": notes, "analysis": analysis, "seconds": round(time.time() - t0, 1),
                "target": target_label, "process": str(cfg.get("print_settings_id") or ""),
                "filament": ctx["filament"].get("preset"), "slot": slot, "flavor": flavor,
                "log": {"ctx": {k: v for k, v in ctx.items() if k != "current"}, "current": ctx["current"],
                        "baseline": out["baseline"], "proposals": out["proposals"], "rejected": out["rejected"]}}

    # ------------------------------------------------------------ save
    def save(self, job, ids, out_path):
        plan = job.plan
        if not plan:
            raise ProjectError("nothing")
        wanted = {int(i) for i in ids}
        chosen = [c for c in plan["changes"] if c["id"] in wanted]
        cfg = copy.deepcopy(plan["cfg"])
        pc = ProjectConfig(cfg, plan["slot"] - 1, filament_map=plan["fmap"])
        keys = pc.apply(chosen)
        if os.path.abspath(out_path) == os.path.abspath(job.path):
            raise ProjectError("same_file")
        plan["base"].write(out_path, settings=cfg, moves=plan["moves"], plate_meta=plan["plate_meta"],
                           app=plan["app"])
        return {"path": out_path, "keys": keys}


def _size(v):
    import numpy as np
    a = np.asarray(v)
    if not len(a):
        return [0, 0, 0]
    return [round(float(x), 1) for x in (a.max(axis=0) - a.min(axis=0))]


def _as_list(v):
    return v if isinstance(v, list) else ([v] if v is not None else [])


def _idx(v, i):
    lst = _as_list(v)
    return str(lst[i]) if i < len(lst) else (str(lst[0]) if lst else "")


def default_output(path, target_label=""):
    base, _ = os.path.splitext(path)
    if base.lower().endswith(".gcode"):
        base = base[:-6]
    return base + "_ayarci.3mf"
