"""A small stand-in for OrcaSlicer's embedded `orca` module, enough to drive the plugin in tests.

It mirrors the real API surface used by 3DsetuPia (names taken from OrcaSlicer's
src/slic3r/plugin/host/*.cpp bindings): host.model(), host.preset_bundle(),
host.preset.{process,filament}.begin_update()/set()/commit(), host.ui.create_dock_panel(),
host.plugin.storage(), host.app_info().
"""
import sys
import types

import numpy as np


class ExecutionResult:
    def __init__(self, ok, text):
        self.ok, self.text = ok, text

    @staticmethod
    def success(text=""):
        return ExecutionResult(True, text)

    @staticmethod
    def failure(level, text=""):
        return ExecutionResult(False, text)


class PluginResult:
    RecoverableError = "RecoverableError"


class _BBox:
    def __init__(self, mn, mx):
        self.min, self.max, self.defined = tuple(mn), tuple(mx), True
        self.size = tuple(np.array(mx) - np.array(mn))


class Mesh:
    def __init__(self, v, t):
        self._v = np.asarray(v, dtype=np.float32)
        self._t = np.asarray(t, dtype=np.int32)
        self._v.setflags(write=False)
        self._t.setflags(write=False)

    def vertices(self):
        return self._v

    def triangles(self):
        return self._t

    def is_empty(self):
        return len(self._t) == 0


class Volume:
    def __init__(self, mesh, part=True, matrix=None):
        self._mesh, self._part = mesh, part
        self._m = np.eye(4) if matrix is None else matrix

    def is_model_part(self):
        return self._part

    def mesh(self):
        return self._mesh

    def matrix(self):
        return self._m.copy()


class Instance:
    def __init__(self, matrix=None, printable=True):
        self._m = np.eye(4) if matrix is None else matrix
        self._p = printable

    def is_printable(self):
        return self._p

    def matrix(self):
        return self._m.copy()


class ModelObject:
    def __init__(self, name, volumes, instances=None, config=None, painted=False):
        self.name, self._vols = name, volumes
        self._inst = instances or [Instance()]
        self._cfg = config or {}
        self._painted = painted
        self.printable = True

    def instances(self):
        return list(self._inst)

    def volumes(self):
        return list(self._vols)

    def config_keys(self):
        return list(self._cfg)

    def is_mm_painted(self):
        return self._painted

    def bounding_box(self):
        pts = np.concatenate([v.mesh().vertices() for v in self._vols])
        return _BBox(pts.min(axis=0), pts.max(axis=0))


class Model:
    def __init__(self, objects):
        self._o = objects

    def objects(self):
        return list(self._o)


class Preset:
    def __init__(self, name, config, user=False, visible=True, compatible=True, default=False):
        self.name, self.config = name, dict(config)
        self._user = user
        self.is_visible, self.is_compatible, self.is_default = visible, compatible, default
        self.is_dirty = False

    def is_user(self):
        return self._user

    def config_value(self, key):
        v = self.config.get(key)
        return None if v is None else str(v)

    def config_keys(self):
        return list(self.config)


class Collection:
    def __init__(self, presets):
        self._p = presets

    def size(self):
        return len(self._p)

    def preset(self, i):
        return self._p[i]

    def find_preset(self, name):
        for p in self._p:
            if p.name == name:
                return p
        return None

    def preset_names(self):
        return [p.name for p in self._p]


class Bundle:
    def __init__(self, process, printer, filaments, slots, bed="Textured PEI Plate"):
        self._proc, self._printer = process, printer
        self.filaments = Collection(filaments)
        self.filament_presets = list(slots)
        self._bed = bed

    def current_process_preset(self):
        return self._proc

    def current_printer_preset(self):
        return self._printer

    def current_filament_presets(self):
        return [self.filaments.find_preset(n) for n in self.filament_presets]

    def current_filament_preset_names(self):
        return list(self.filament_presets)

    def full_config_value(self, key):
        return self._bed if key == "curr_bed_type" else None


class _Result:
    def __init__(self, cat, target, keys):
        self.category, self.target_name, self.keys = cat, target, keys
        self.dirty, self.selection_changed, self.shared_slots = True, False, [1]


class Transaction:
    def __init__(self, host, cat, preset, slot=None):
        self.host, self.cat, self.preset, self.slot = host, cat, preset, slot
        self.staged = {}

    def set(self, key, value):
        if key in self.staged:
            raise ValueError("duplicate key")
        if not isinstance(value, str):
            raise TypeError("value must be a serialized string")
        self.staged[key] = value

    def commit(self):
        for k in self.staged:
            if k not in self.preset.config:
                raise ValueError("unknown key %s" % k)
        self.preset.config.update(self.staged)
        self.preset.is_dirty = True
        self.host.commits.append((self.cat, self.preset.name, dict(self.staged)))
        return _Result(self.cat, self.preset.name, list(self.staged))


class Editor:
    def __init__(self, host, cat):
        self.host, self.cat = host, cat

    def begin_update(self, *args):
        b = self.host.bundle
        if self.cat == "process":
            name = args[0] if args else ""
            if name and name != b._proc.name:
                raise ValueError("unavailable target")
            return Transaction(self.host, "process", b._proc)
        slot = args[0]
        name = args[1] if len(args) > 1 else ""
        if name:
            p = b.filaments.find_preset(name)
            if p is None:
                raise ValueError("unknown filament")
            b.filament_presets[slot - 1] = name
        p = b.filaments.find_preset(b.filament_presets[slot - 1])
        return Transaction(self.host, "filament", p, slot)


class Panel:
    def __init__(self, host, on_message, on_close):
        self.host, self.on_message, self.on_close = host, on_message, on_close
        self.open = True
        self.posted = []

    def post(self, data):
        import json
        json.dumps(data)  # the real bridge serializes to JSON; fail loudly on numpy types
        self.posted.append(data)

    def is_open(self):
        return self.open

    def show(self):
        pass

    def close(self):
        self.open = False
        self.on_close()


class Host:
    def __init__(self, storage):
        self.storage_dir = storage
        self.commits = []
        self.panel = None
        self.bundle = None
        self.model_obj = Model([])
        host = self

        class _UI:
            @staticmethod
            def create_dock_panel(html, title, width, height, on_message, on_close, dock):
                assert "<html" in html
                host.panel = Panel(host, on_message, on_close)
                return host.panel

            @staticmethod
            def create_window(**kw):
                return _UI.create_dock_panel(kw["html"], kw.get("title"), 0, 0, kw["on_message"],
                                             kw["on_close"], "float")

        class _Plugin:
            @staticmethod
            def storage():
                return host.storage_dir

        self.ui = _UI()
        self.plugin = _Plugin()
        self.preset = types.SimpleNamespace(process=Editor(self, "process"), filament=Editor(self, "filament"))

    def model(self):
        return self.model_obj

    def preset_bundle(self):
        return self.bundle

    def app_info(self):
        return {"version": "2.5.0-test", "language": "tr_TR"}


def install(storage):
    mod = types.ModuleType("orca")
    mod.ExecutionResult = ExecutionResult
    mod.PluginResult = PluginResult
    mod.script = types.SimpleNamespace(ScriptPluginCapabilityBase=object)
    mod.base = object
    mod.registered = []
    def _plugin(cls):
        cls().register_capabilities()   # the real host does this after import
        return cls
    mod.plugin = _plugin
    mod.register_capability = lambda cls: mod.registered.append(cls)
    mod.host = Host(storage)
    sys.modules["orca"] = mod
    return mod
