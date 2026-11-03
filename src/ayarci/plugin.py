"""3DsetuPia - OrcaSlicer glue: panel, snapshots, worker, apply/undo.

Threading model (see OrcaSlicer docs/HLSD/python-plugin-async-bridge.md):
* execute() runs on the background Script worker. It opens the panel and then
  serves a command queue: heavy work (mesh analysis, AI calls) and preset edits
  (begin_update/set/commit must run on this worker) happen here.
* on_message() runs on the UI thread. It only reads live objects (model,
  presets) into plain copies and enqueues work. It never blocks on the network.
"""

import json
import os
import queue
import time
import traceback

import numpy as np
import orca

from .catalog import SETTINGS, PAGES, PAGE_ORDER, CONTEXT_KEYS_PRINTER, CONTEXT_KEYS_FILAMENT  # bundle:strip
from .geometry import analyze_plate  # bundle:strip
from .rules import INTENTS  # bundle:strip
from .providers import PROVIDERS, ProviderError, public_meta, list_models, resolve  # bundle:strip
from .assist import (Store, active_config, masked_settings, update_settings,  # bundle:strip
                     provider_error_text, suggest, _plain)  # bundle:strip
from .i18n import msg  # bundle:strip
from .ui import UI_HTML  # bundle:strip

PLUGIN_VERSION = "1.1.0"
REPO_URL = "https://github.com/Keanyy/3DsetuPia"
MIN_ORCA = "2.5.0-beta"
MIN_VERSION_TEXT = ("3DsetuPia için OrcaSlicer %s veya daha yeni bir sürüm gerekiyor. / "
                    "3DsetuPia needs OrcaSlicer %s or newer." % (MIN_ORCA, MIN_ORCA))


def _lang_from_code(code):
    return "tr" if str(code or "").lower().startswith("tr") else "en"


# ------------------------------------------------------------------ snapshots (UI thread)

def snapshot_presets(chosen_filament=""):
    bundle = orca.host.preset_bundle()
    proc = bundle.current_process_preset()
    printer = bundle.current_printer_preset()
    fil_presets = list(bundle.current_filament_presets())
    fil_names = list(bundle.current_filament_preset_names())
    slot1 = fil_presets[0] if fil_presets else None
    fil = slot1
    if chosen_filament and (slot1 is None or chosen_filament != slot1.name):
        found = bundle.filaments.find_preset(chosen_filament)
        if found is not None:
            fil = found
    current = {}
    for key, entry in SETTINGS.items():
        src = proc if entry["cat"] == "process" else fil
        if src is None:
            continue
        val = src.config_value(key)
        if val is not None:
            current[key] = str(val)
    printer_info = {k: printer.config_value(k) for k in CONTEXT_KEYS_PRINTER}
    printer_info["preset"] = printer.name
    fil_info = {}
    if fil is not None:
        fil_info = {k: fil.config_value(k) for k in CONTEXT_KEYS_FILAMENT}
        fil_info["preset"] = fil.name
    bed = None
    try:
        bed = bundle.full_config_value("curr_bed_type")
    except Exception:
        bed = None
    choices = []
    coll = bundle.filaments
    for i in range(coll.size()):
        p = coll.preset(i)
        if p.is_default or not p.is_visible or not p.is_compatible:
            continue
        choices.append({"name": p.name, "user": bool(p.is_user())})
    choices.sort(key=lambda c: (not c["user"], c["name"].lower()))
    return {
        "current": current,
        "printer": _plain(printer_info),
        "filament": _plain(fil_info),
        "bed_type": bed or "",
        "process_name": proc.name,
        "process_dirty": bool(proc.is_dirty),
        "filament_slot1": slot1.name if slot1 is not None else (fil_names[0] if fil_names else ""),
        "filament_selected": fil.name if fil is not None else "",
        "filament_slots": len(fil_names),
        "filament_choices": choices,
    }


def snapshot_model():
    model = orca.host.model()
    parts, objects, overrides = [], [], []
    seen = {}
    for idx, obj in enumerate(model.objects()):
        instances = [inst for inst in obj.instances() if inst.is_printable()]
        if not instances:
            continue
        name = obj.name or ("Nesne %d" % (idx + 1))
        if name in seen:
            seen[name] += 1
            name = "%s #%d" % (name, seen[name])
        else:
            seen[name] = 1
        im = np.array(instances[0].matrix(), dtype=np.float64)
        tri_count = 0
        for vol in obj.volumes():
            if not vol.is_model_part():
                continue
            mesh = vol.mesh()
            if mesh.is_empty():
                continue
            v = np.array(mesh.vertices(), dtype=np.float32, copy=True)
            t = np.array(mesh.triangles(), dtype=np.int32, copy=True)
            vm = np.array(vol.matrix(), dtype=np.float64)
            parts.append({"object": name, "vertices": v, "triangles": t, "matrix": im @ vm})
            tri_count += len(t)
        try:
            keys = [k for k in obj.config_keys() if k in SETTINGS]
        except Exception:
            keys = []
        if keys:
            overrides.append({"object": name, "keys": keys})
        objects.append({"name": name, "instances": len(instances), "triangles": tri_count,
                        "painted": bool(obj.is_mm_painted()) if hasattr(obj, "is_mm_painted") else False})
    return parts, objects, overrides


# ------------------------------------------------------------------ the capability

class AyarciAssistant(orca.script.ScriptPluginCapabilityBase):
    panel = None
    _commands = None
    _cancelled = False

    def get_name(self):
        return "3DsetuPia – AI baskı ayarı asistanı"

    # ---------------- worker ----------------
    def execute(self):
        # OrcaSlicer 2.5.0-alpha ran Script plugins on the UI thread and had no preset write API;
        # this plugin's command loop would freeze the app there. Both arrived together in
        # 2.5.0-beta, so the write API doubles as the "runs on a worker" check.
        if not self._capabilities()["can_write"]:
            return orca.ExecutionResult.failure(orca.PluginResult.RecoverableError, MIN_VERSION_TEXT)
        if self.panel is not None and self.panel.is_open():
            try:
                self.panel.show()
            except Exception:
                pass
            return orca.ExecutionResult.success("3DsetuPia zaten açık.")
        commands = queue.Queue()
        self._commands = commands
        self._last = None          # last validated proposal set (worker side, authoritative)
        self._undo = None
        try:
            folder = orca.host.plugin.storage()
        except Exception:
            folder = ""
        self.store = Store(folder)
        self.settings = self.store.load()
        try:
            if self._cancelled:
                return orca.ExecutionResult.success("3DsetuPia kapatıldı.")
            self.panel = self._open_panel()
            while True:
                item = commands.get()
                cmd = item.get("command")
                if self._cancelled or cmd == "close":
                    return orca.ExecutionResult.success("3DsetuPia kapatıldı.")
                try:
                    if cmd == "analyze":
                        self._do_analyze(item)
                    elif cmd == "apply":
                        self._do_apply(item)
                    elif cmd == "undo":
                        self._do_undo(item)
                    elif cmd == "test":
                        self._do_test(item)
                except Exception as exc:  # never let one command kill the panel
                    self._post({"command": "error", "text": "%s: %s" % (type(exc).__name__, exc),
                                "trace": traceback.format_exc()[-1500:]})
        except Exception as exc:
            return orca.ExecutionResult.failure(orca.PluginResult.RecoverableError,
                                                "3DsetuPia hata verdi: %s" % exc)
        finally:
            if self._commands is commands:
                self._commands = None
            self.panel = None

    def _open_panel(self):
        ui = orca.host.ui
        if hasattr(ui, "create_dock_panel"):
            try:
                return ui.create_dock_panel(html=UI_HTML, title="3DsetuPia – AI", width=460, height=760,
                                            on_message=self._on_message, on_close=self._on_close,
                                            dock="right")
            except Exception:
                pass
        return ui.create_window(title="3DsetuPia – AI baskı ayarı asistanı", html=UI_HTML, width=980,
                                height=760, on_message=self._on_message, on_close=self._on_close)

    def _post(self, data):
        panel = self.panel
        if panel is not None and panel.is_open():
            panel.post(_plain(data))

    def _lang(self):
        return self.settings.get("lang") or "tr"

    # ---------------- UI thread ----------------
    def _on_message(self, message):
        message = dict(message) if isinstance(message, dict) else {}
        cmd = message.get("command")
        try:
            if cmd == "init":
                self._post(self._init_state())
            elif cmd == "refresh":
                self._post(self._scene_state(message.get("filament", "")))
            elif cmd == "save_settings":
                self._save_settings(message)
            elif cmd == "set_lang":
                self.settings["lang"] = "tr" if message.get("lang") == "tr" else "en"
                self.store.save(self.settings)
                self._post(self._init_state())
            elif cmd == "analyze":
                parts, objects, overrides = snapshot_model()
                presets = snapshot_presets(message.get("filament", ""))
                self._enqueue({"command": "analyze", "parts": parts, "objects": objects,
                               "overrides": overrides, "presets": presets,
                               "intent": message.get("intent", "balanced"),
                               "note": str(message.get("note", ""))[:500],
                               "use_ai": bool(message.get("use_ai", True))})
            elif cmd in ("apply", "undo"):
                bundle = orca.host.preset_bundle()
                names = list(bundle.current_filament_preset_names())
                message["live_process"] = bundle.current_process_preset().name
                message["live_slot1"] = names[0] if names else ""
                self._enqueue(message)
            elif cmd == "test":
                self._enqueue(message)
        except Exception as exc:
            self._post({"command": "error", "text": "%s: %s" % (type(exc).__name__, exc),
                        "trace": traceback.format_exc()[-1500:]})

    def _on_close(self):
        self._enqueue({"command": "close"})

    def on_cancelled(self):
        self._cancelled = True
        self._enqueue({"command": "close"})

    def _enqueue(self, item):
        q = self._commands
        if q is not None:
            q.put(item)

    def _capabilities(self):
        can_write = hasattr(orca.host, "preset") and hasattr(getattr(orca.host.preset, "process", None),
                                                             "begin_update")
        return {"can_write": bool(can_write)}

    def _init_state(self):
        info = {}
        try:
            info = dict(orca.host.app_info())
        except Exception:
            pass
        if not self.settings.get("lang"):
            self.settings["lang"] = _lang_from_code(info.get("language"))
        state = {"command": "init", "version": PLUGIN_VERSION, "orca_version": info.get("version", ""),
                 "lang": self._lang(), "providers": public_meta(self._lang()),
                 "settings": masked_settings(self.settings), "caps": self._capabilities(),
                 "pages": {k: v.get(self._lang(), v["en"]) for k, v in PAGES.items()},
                 "page_order": PAGE_ORDER, "storage": self.store.folder, "repo": REPO_URL}
        scene = self._scene_state("")
        scene.pop("command", None)
        state.update(scene)
        return state

    def _scene_state(self, chosen):
        out = {"command": "scene"}
        try:
            _, objects, overrides = snapshot_model_light()
            out["objects"] = objects
            out["overrides"] = overrides
        except Exception as exc:
            out["objects"] = []
            out["scene_error"] = str(exc)
        try:
            p = snapshot_presets(chosen)
            out.update({"process_name": p["process_name"], "printer_name": p["printer"].get("preset", ""),
                        "nozzle": p["printer"].get("nozzle_diameter"), "bed_type": p["bed_type"],
                        "filament_slot1": p["filament_slot1"], "filament_selected": p["filament_selected"],
                        "filament_slots": p["filament_slots"], "filament_choices": p["filament_choices"],
                        "filament_type": p["filament"].get("filament_type")})
        except Exception as exc:
            out["preset_error"] = str(exc)
        return out

    def _save_settings(self, message):
        update_settings(self.settings, message)
        ok = self.store.save(self.settings)
        self._post({"command": "settings_saved", "ok": ok, "settings": masked_settings(self.settings)})

    # ---------------- worker commands ----------------
    def _do_test(self, item):
        lang = self._lang()
        cfg = active_config(self.settings)
        try:
            if cfg["provider"] == "none":
                self._post({"command": "test_result", "ok": True, "models": [],
                            "text": msg(lang, "test_none")})
                return
            resolve(cfg)
            models = list_models(cfg)
            per = self.settings.setdefault("providers", {}).setdefault(cfg["provider"], {})
            per["tested"] = True
            if not per.get("model") and models:
                default = PROVIDERS[cfg["provider"]]["default_model"]
                per["model"] = default if default in models else ""
            self.store.save(self.settings)
            self._post({"command": "test_result", "ok": True, "models": models[:300],
                        "settings": masked_settings(self.settings),
                        "text": msg(lang, "test_ok", n=len(models))})
        except ProviderError as exc:
            self._post({"command": "test_result", "ok": False,
                        "text": self._provider_error_text(exc, cfg), "kind": exc.kind})

    def _provider_error_text(self, exc, cfg):
        return provider_error_text(self._lang(), exc, cfg)

    def _do_analyze(self, item):
        lang = self._lang()
        t0 = time.time()
        presets = item["presets"]
        ctx = {"lang": lang, "intent": item.get("intent") if item.get("intent") in INTENTS else "balanced",
               "note": item.get("note", ""), "current": presets["current"], "printer": presets["printer"],
               "filament": presets["filament"], "bed_type": presets["bed_type"]}
        if not item["parts"]:
            self._post({"command": "proposals", "ok": False, "text": msg(lang, "no_model")})
            return
        self._post({"command": "progress", "text": msg(lang, "measuring")})
        analysis = analyze_plate(item["parts"])
        cfg = active_config(self.settings)
        out = suggest(analysis, ctx, cfg, item.get("use_ai", True),
                      progress=lambda text: self._post({"command": "progress", "text": text}))
        source, summary, changes = out["source"], out["summary"], out["changes"]
        baseline, proposals, rejected = out["baseline"], out["proposals"], out["rejected"]
        warnings = out["warnings"]
        if item.get("overrides"):
            names = ", ".join(o["object"] for o in item["overrides"][:4])
            warnings.append(msg(lang, "object_overrides", names=names))
        if presets.get("filament_slots", 1) > 1:
            warnings.append(msg(lang, "multi_filament"))
        if any(o.get("painted") for o in item.get("objects", [])):
            warnings.append(msg(lang, "painted"))
        self._last = {"changes": changes, "presets": presets, "chosen_filament": presets["filament_selected"],
                      "process_name": presets["process_name"]}
        result = {"command": "proposals", "ok": True, "source": source, "summary": summary,
                  "changes": changes, "warnings": warnings, "analysis": analysis,
                  "seconds": round(time.time() - t0, 1),
                  "filament_switch": presets["filament_selected"] != presets["filament_slot1"],
                  "filament_from": presets["filament_slot1"], "filament_to": presets["filament_selected"]}
        self.store.write_last_run({"ctx": {k: v for k, v in ctx.items() if k != "current"},
                                   "current": ctx["current"], "analysis": analysis, "baseline": baseline,
                                   "proposals": proposals, "changes": changes, "rejected": rejected,
                                   "warnings": warnings, "provider": cfg["provider"], "model": cfg["model"]})
        self._post(result)

    def _do_apply(self, item):
        lang = self._lang()
        if not self._capabilities()["can_write"]:
            self._post({"command": "applied", "ok": False, "text": msg(lang, "no_write_api")})
            return
        last = self._last
        if not last:
            self._post({"command": "applied", "ok": False, "text": msg(lang, "nothing")})
            return
        slot1_then = last["presets"]["filament_slot1"]
        if item.get("live_process") and item["live_process"] != last["process_name"] or \
                item.get("live_slot1") is not None and item.get("live_slot1") != slot1_then:
            self._post({"command": "applied", "ok": False, "text": msg(lang, "stale")})
            return
        wanted = {int(i) for i in item.get("ids", []) if str(i).isdigit() or isinstance(i, int)}
        chosen = [c for c in last["changes"] if c["id"] in wanted]
        other_filament = last["chosen_filament"] != slot1_then
        switch_filament = bool(item.get("switch_filament")) and other_filament
        if other_filament and not switch_filament:
            # filament suggestions were computed for the other filament; do not write them
            # into the filament that is actually in slot 1
            chosen = [c for c in chosen if c["cat"] != "filament"]
        if not chosen and not switch_filament:
            self._post({"command": "applied", "ok": False, "text": msg(lang, "nothing_selected")})
            return
        undo = {"process": None, "filament": None}
        done = []
        try:
            proc = [c for c in chosen if c["cat"] == "process"]
            fil = [c for c in chosen if c["cat"] == "filament"]
            if fil or switch_filament:
                target = last["chosen_filament"] if switch_filament else ""
                tx = orca.host.preset.filament.begin_update(1, target)
                for c in fil:
                    tx.set(c["key"], c["new"])
                res = tx.commit()
                undo["filament"] = {"target": res.target_name,
                                    "values": [(c["key"], c["old"]) for c in fil],
                                    "previous": slot1_then if switch_filament else ""}
                done += [c["key"] for c in fil]
                if switch_filament:
                    done.append("filament_settings_id")
            if proc:
                tx = orca.host.preset.process.begin_update("")
                for c in proc:
                    tx.set(c["key"], c["new"])
                res = tx.commit()
                undo["process"] = {"target": res.target_name,
                                   "values": [(c["key"], c["old"]) for c in proc]}
                done += [c["key"] for c in proc]
        except Exception as exc:
            self._undo = undo if (undo["process"] or undo["filament"]) else None
            key = "apply_partial" if (undo["process"] or undo["filament"]) else "apply_failed"
            self._post({"command": "applied", "ok": False, "partial": done,
                        "text": msg(lang, key, detail=str(exc), n=len(done))})
            return
        self._undo = undo
        self._post({"command": "applied", "ok": True, "keys": done,
                    "text": msg(lang, "applied", n=len(done))})

    def _do_undo(self, item):
        lang = self._lang()
        undo = self._undo
        if not undo:
            self._post({"command": "undone", "ok": False, "text": msg(lang, "nothing_to_undo")})
            return
        try:
            if undo.get("process") and undo["process"]["values"]:
                tx = orca.host.preset.process.begin_update(undo["process"]["target"])
                for k, v in undo["process"]["values"]:
                    tx.set(k, v)
                tx.commit()
            fu = undo.get("filament")
            if fu and fu["values"]:
                tx = orca.host.preset.filament.begin_update(1, fu["target"])
                for k, v in fu["values"]:
                    tx.set(k, v)
                tx.commit()
            if fu and fu.get("previous"):
                # put the originally loaded filament back into slot 1 (selection happens in begin_update)
                tx = orca.host.preset.filament.begin_update(1, fu["previous"])
                try:
                    tx.commit()
                except Exception:
                    pass
        except Exception as exc:
            self._post({"command": "undone", "ok": False, "text": msg(lang, "undo_failed", detail=str(exc))})
            return
        self._undo = None
        self._post({"command": "undone", "ok": True, "text": msg(lang, "undone")})


def snapshot_model_light():
    """Object list only (no mesh copies) for the panel header."""
    model = orca.host.model()
    objects, overrides = [], []
    for idx, obj in enumerate(model.objects()):
        printable = [inst for inst in obj.instances() if inst.is_printable()]
        if not printable:
            continue
        name = obj.name or ("Nesne %d" % (idx + 1))
        bb = obj.bounding_box()
        size = list(bb.size) if bb is not None and bb.defined else [0, 0, 0]
        objects.append({"name": name, "instances": len(printable),
                        "size_mm": [round(float(s), 1) for s in size]})
        try:
            keys = [k for k in obj.config_keys() if k in SETTINGS]
        except Exception:
            keys = []
        if keys:
            overrides.append({"object": name, "keys": keys})
    return None, objects, overrides


@orca.plugin
class AyarciPackage(orca.base):
    def register_capabilities(self):
        orca.register_capability(AyarciAssistant)
