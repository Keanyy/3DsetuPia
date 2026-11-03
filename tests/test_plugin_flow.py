"""End-to-end: drive the real plugin code against a fake OrcaSlicer host."""
import importlib
import importlib.util
import sys
import threading
import time

import pytest

import fake_orca
import fake_server
import meshes as M
from fixtures import PROCESS, PLA, PETG, PRINTER


def wait_for(panel, command, timeout=60, start=0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for m in panel.posted[start:]:
            if m.get("command") == command:
                return m
        time.sleep(0.02)
    raise AssertionError("no %s message; got %s" % (command, [m.get("command") for m in panel.posted]))


def setup_scene(orca, objects):
    host = orca.host
    pla = fake_orca.Preset("Bambu PLA Basic @BBL P1S", PLA)
    petg = fake_orca.Preset("Elegoo PETG @base", PETG, user=True)
    hidden = fake_orca.Preset("Hidden", PLA, visible=False)
    host.bundle = fake_orca.Bundle(fake_orca.Preset("0.20mm Standard @BBL P1S", PROCESS),
                                   fake_orca.Preset("Bambu Lab P1S 0.4 nozzle", PRINTER),
                                   [pla, petg, hidden], [pla.name])
    host.model_obj = fake_orca.Model(objects)


def obj(name, mesh, **kw):
    v, t = mesh
    return fake_orca.ModelObject(name, [fake_orca.Volume(fake_orca.Mesh(v, t))], **kw)


@pytest.fixture
def plugin_env(tmp_path, request):
    module_name = getattr(request, "param", "ayarci.plugin")
    orca = fake_orca.install(str(tmp_path))
    for m in [k for k in list(sys.modules) if k.startswith("ayarci") or k == "ayarci_bundle"]:
        del sys.modules[m]
    if module_name == "bundle":
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("ayarci_bundle", request.config.rootpath / "dist" / "ayarci.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
    else:
        mod = importlib.import_module(module_name)
    cap_cls = orca.registered[-1]
    cap = cap_cls()
    yield orca, mod, cap
    cap._enqueue({"command": "close"})


def start(orca, cap):
    th = threading.Thread(target=cap.execute, daemon=True)
    th.start()
    t0 = time.time()
    while orca.host.panel is None and time.time() - t0 < 5:
        time.sleep(0.01)
    return orca.host.panel


MUSHROOM = M.merge(M.cylinder(3, 30), M.cylinder(25, 5, oz=30))


@pytest.mark.parametrize("plugin_env", ["ayarci.plugin", "bundle"], indirect=True)
def test_rules_mode_analyze_apply_undo(plugin_env):
    orca, mod, cap = plugin_env
    setup_scene(orca, [obj("mantar", MUSHROOM)])
    panel = start(orca, cap)
    panel.on_message({"command": "init"})
    init = wait_for(panel, "init")
    assert init["lang"] == "tr" and init["objects"][0]["name"] == "mantar"
    names = [c["name"] for c in init["filament_choices"]]
    assert "Hidden" not in names and names[0] == "Elegoo PETG @base"   # user presets first

    n = len(panel.posted)
    panel.on_message({"command": "analyze", "intent": "looks", "note": "", "filament": ""})
    prop = wait_for(panel, "proposals", start=n)
    assert prop["ok"] and prop["source"] == "rules"
    keys = {c["key"] for c in prop["changes"]}
    assert "enable_support" in keys and "layer_height" in keys

    n = len(panel.posted)
    panel.on_message({"command": "apply", "ids": [c["id"] for c in prop["changes"]]})
    res = wait_for(panel, "applied", start=n)
    assert res["ok"], res
    proc = orca.host.bundle.current_process_preset()
    assert proc.config["enable_support"] == "1"
    assert proc.config["layer_height"] == "0.12"
    assert proc.is_dirty
    assert all(isinstance(v, str) for _, _, staged in orca.host.commits for v in staged.values())

    n = len(panel.posted)
    panel.on_message({"command": "undo"})
    und = wait_for(panel, "undone", start=n)
    assert und["ok"]
    assert proc.config["enable_support"] == "0" and proc.config["layer_height"] == "0.2"


@pytest.mark.parametrize("plugin_env", ["ayarci.plugin"], indirect=True)
def test_filament_switch_and_filament_keys(plugin_env):
    orca, mod, cap = plugin_env
    setup_scene(orca, [obj("kutu", M.box(40, 40, 20))])
    panel = start(orca, cap)
    panel.on_message({"command": "init"})
    wait_for(panel, "init")
    n = len(panel.posted)
    panel.on_message({"command": "analyze", "intent": "balanced", "filament": "Elegoo PETG @base"})
    prop = wait_for(panel, "proposals", start=n)
    assert prop["filament_switch"] and prop["filament_to"] == "Elegoo PETG @base"
    fil_changes = [c for c in prop["changes"] if c["cat"] == "filament"]
    assert any(c["key"] == "fan_max_speed" for c in fil_changes)
    n = len(panel.posted)
    panel.on_message({"command": "apply", "ids": [c["id"] for c in prop["changes"]], "switch_filament": True})
    assert wait_for(panel, "applied", start=n)["ok"]
    assert orca.host.bundle.filament_presets[0] == "Elegoo PETG @base"
    assert orca.host.bundle.filaments.find_preset("Elegoo PETG @base").config["fan_max_speed"] == "50"


@pytest.mark.parametrize("plugin_env", ["ayarci.plugin"], indirect=True)
def test_ai_mode_with_openai_compatible_server(plugin_env):
    orca, mod, cap = plugin_env
    srv, state, url = fake_server.start()
    try:
        setup_scene(orca, [obj("figur", M.sphere(20), painted=True, config={"wall_loops": "3"})])
        panel = start(orca, cap)
        panel.on_message({"command": "init"})
        wait_for(panel, "init")
        panel.on_message({"command": "save_settings", "provider": "custom", "base_url": url + "/v1",
                          "api_key": "sk-secret-1234", "model": "model-a"})
        saved = wait_for(panel, "settings_saved")
        assert "sk-secret" not in str(saved)                 # key never sent to the page
        assert saved["settings"]["providers"]["custom"]["key_hint"] == "…1234"
        n = len(panel.posted)
        panel.on_message({"command": "test"})
        tr = wait_for(panel, "test_result", start=n)
        assert tr["ok"] and tr["models"] == ["model-a", "model-b"]
        n = len(panel.posted)
        panel.on_message({"command": "analyze", "intent": "balanced", "filament": ""})
        prop = wait_for(panel, "proposals", start=n)
        assert prop["source"] == "ai" and prop["summary"] == "Test özeti"
        keys = {c["key"] for c in prop["changes"]}
        assert keys == {"wall_loops", "layer_height"}       # G-code suggestion filtered out
        text = " ".join(prop["warnings"])
        assert "güvenlik" in text and "kendine özel" in text and "boyama" in text
        # what was sent to the AI: measurements, not the mesh
        sent = [r for r in state.requests if r[0] == "POST"][-1][3]
        assert "vertices" not in str(sent) and "settings_you_may_change" in str(sent)
        import json, os
        log = json.load(open(os.path.join(orca.host.storage_dir, "ayarci_last_run.json"), encoding="utf-8"))
        assert "sk-secret" not in json.dumps(log)
    finally:
        srv.shutdown()


@pytest.mark.parametrize("plugin_env", ["ayarci.plugin"], indirect=True)
def test_ai_failure_falls_back_to_rules(plugin_env):
    orca, mod, cap = plugin_env
    setup_scene(orca, [obj("kule", M.cylinder(4, 120))])
    panel = start(orca, cap)
    panel.on_message({"command": "save_settings", "provider": "custom",
                      "base_url": "http://127.0.0.1:9/v1", "model": "m"})
    wait_for(panel, "settings_saved")
    n = len(panel.posted)
    panel.on_message({"command": "analyze", "intent": "balanced", "filament": ""})
    prop = wait_for(panel, "proposals", start=n, timeout=90)
    assert prop["ok"] and prop["source"] == "rules"
    assert any("yerel kurallar" in w.lower() for w in prop["warnings"])
    assert any(c["key"] == "brim_type" for c in prop["changes"])


@pytest.mark.parametrize("plugin_env", ["ayarci.plugin"], indirect=True)
def test_empty_plate(plugin_env):
    orca, mod, cap = plugin_env
    setup_scene(orca, [])
    panel = start(orca, cap)
    n = len(panel.posted)
    panel.on_message({"command": "analyze", "intent": "balanced"})
    prop = wait_for(panel, "proposals", start=n)
    assert not prop["ok"]


@pytest.mark.parametrize("plugin_env", ["ayarci.plugin"], indirect=True)
def test_old_orca_without_worker_refuses_to_start(plugin_env):
    orca, mod, cap = plugin_env
    setup_scene(orca, [obj("k", M.box(10, 10, 10))])
    del orca.host.preset                     # 2.5.0-alpha: no write API, Script on the UI thread
    res = cap.execute()                      # must return immediately, never block
    assert not res.ok and "2.5.0-beta" in res.text
    assert orca.host.panel is None


@pytest.mark.parametrize("plugin_env", ["ayarci.plugin"], indirect=True)
def test_object_without_printable_instance_is_ignored(plugin_env):
    orca, mod, cap = plugin_env
    o = obj("gizli", M.box(10, 10, 10))
    o._inst = [fake_orca.Instance(printable=False)]
    setup_scene(orca, [o, obj("görünür", M.box(20, 20, 20))])
    panel = start(orca, cap)
    panel.on_message({"command": "init"})
    init = wait_for(panel, "init")
    assert [x["name"] for x in init["objects"]] == ["görünür"]


@pytest.mark.parametrize("plugin_env", ["ayarci.plugin"], indirect=True)
def test_switch_then_undo_restores_original_filament(plugin_env):
    orca, mod, cap = plugin_env
    setup_scene(orca, [obj("kutu", M.box(40, 40, 20))])
    panel = start(orca, cap)
    n = len(panel.posted)
    panel.on_message({"command": "analyze", "intent": "balanced", "filament": "Elegoo PETG @base"})
    prop = wait_for(panel, "proposals", start=n)
    n = len(panel.posted)
    panel.on_message({"command": "apply", "ids": [c["id"] for c in prop["changes"]], "switch_filament": True})
    assert wait_for(panel, "applied", start=n)["ok"]
    assert orca.host.bundle.filament_presets[0] == "Elegoo PETG @base"
    n = len(panel.posted)
    panel.on_message({"command": "undo"})
    assert wait_for(panel, "undone", start=n)["ok"]
    assert orca.host.bundle.filament_presets[0] == "Bambu PLA Basic @BBL P1S"
    assert orca.host.bundle.filaments.find_preset("Elegoo PETG @base").config["fan_max_speed"] == "90"


@pytest.mark.parametrize("plugin_env", ["ayarci.plugin"], indirect=True)
def test_filament_changes_not_written_into_wrong_filament(plugin_env):
    orca, mod, cap = plugin_env
    setup_scene(orca, [obj("kutu", M.box(40, 40, 20))])
    panel = start(orca, cap)
    n = len(panel.posted)
    panel.on_message({"command": "analyze", "intent": "balanced", "filament": "Elegoo PETG @base"})
    prop = wait_for(panel, "proposals", start=n)
    assert any(c["cat"] == "filament" for c in prop["changes"])
    n = len(panel.posted)
    # user unticks the filament switch but keeps the PETG fan suggestions ticked
    panel.on_message({"command": "apply", "ids": [c["id"] for c in prop["changes"]], "switch_filament": False})
    wait_for(panel, "applied", start=n)
    pla = orca.host.bundle.filaments.find_preset("Bambu PLA Basic @BBL P1S")
    assert pla.config["fan_max_speed"] == "100"           # PLA untouched
    assert not any(c[0] == "filament" for c in orca.host.commits)


@pytest.mark.parametrize("plugin_env", ["ayarci.plugin"], indirect=True)
def test_stale_suggestions_are_refused(plugin_env):
    orca, mod, cap = plugin_env
    setup_scene(orca, [obj("kutu", M.box(40, 40, 20))])
    panel = start(orca, cap)
    n = len(panel.posted)
    panel.on_message({"command": "analyze", "intent": "looks"})
    prop = wait_for(panel, "proposals", start=n)
    orca.host.bundle._proc.name = "0.12mm Fine @BBL P1S"     # user switched process profile meanwhile
    n = len(panel.posted)
    panel.on_message({"command": "apply", "ids": [c["id"] for c in prop["changes"]]})
    res = wait_for(panel, "applied", start=n)
    assert not res["ok"] and "tekrar" in res["text"]
    assert orca.host.commits == []
