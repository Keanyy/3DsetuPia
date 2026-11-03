import json
import zipfile

import numpy as np
import pytest

from ayarci.engine import Engine, default_output
from ayarci.threemf import Project, ProjectError
from fixtures import PROCESS, PLA
from meshes import box, cylinder
from profilelib import make_library


@pytest.fixture
def engine(tmp_path):
    appdata = tmp_path / "appdata"
    make_library(str(appdata))
    return Engine(str(tmp_path / "cache"), appdata=str(appdata))


def _write_stl(path, v, t):
    tri = v[t]
    data = bytearray(80) + len(tri).to_bytes(4, "little")
    for f in tri:
        data += np.zeros(3, np.float32).tobytes() + f.astype(np.float32).tobytes() + b"\0\0"
    path.write_bytes(bytes(data))


def test_stl_to_new_project(engine, tmp_path):
    v, t = cylinder(4, 80)
    stl = tmp_path / "kule.stl"
    _write_stl(stl, v, t)
    job = engine.open(str(stl))
    info = engine.describe(job)
    assert not info["has_settings"] and info["objects"][0]["name"] == "kule.stl"
    printers = engine.printers()
    assert any(p["id"] == "qidi|Acme P1 0.4 nozzle" for p in printers)
    with pytest.raises(ProjectError):
        engine.prepare(job, "same")
    r = engine.prepare(job, "qidi|Acme P1 0.4 nozzle", intent="strength")
    assert r["ok"] and r["process"] == "0.20mm Standard @Acme P1" and r["flavor"] == "qidi"
    assert any("ortasına" in n for n in r["notes"])
    keys = {c["key"] for c in r["changes"]}
    assert "wall_loops" in keys and "brim_type" in keys            # tall, thin -> brim
    out = tmp_path / "kule_3d.3mf"
    engine.save(job, [c["id"] for c in r["changes"]], str(out))
    q = Project.load(str(out))
    assert q.settings["printer_settings_id"] == "Acme P1 0.4 nozzle" and q.app.startswith("QIDIStudio-")
    assert q.settings["wall_loops"] != PROCESS["wall_loops"]
    lo, hi = q.item_bounds(q.items[0])
    assert np.allclose((lo[:2] + hi[:2]) / 2, (110, 100), atol=0.01) and abs(lo[2]) < 1e-6


def test_project_same_printer_keeps_everything_else(engine, tmp_path):
    from ayarci.meshfiles import build_project
    cfg = engine.library("qidi").build_config("Acme P1 0.4 nozzle", "0.20mm Standard @Acme P1",
                                              ["Acme PLA @P1", "Generic PETG @P1"])
    v, t = box(30, 30, 10)
    src = build_project([{"name": "A", "vertices": v, "triangles": t}], cfg, "QIDIStudio-02.07.00.01", [(80, 80)])
    path = tmp_path / "proj.3mf"
    src.write(str(path))
    job = engine.open(str(path))
    info = engine.describe(job)
    assert info["same_printer_id"] == "qidi|Acme P1 0.4 nozzle" and len(info["filaments"]) == 2
    r = engine.prepare(job, "same", slot=2, intent="looks")
    assert r["filament"] == "Generic PETG @P1"
    out = tmp_path / default_output(str(path)).rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    engine.save(job, [c["id"] for c in r["changes"]], str(out))
    a, b = zipfile.ZipFile(str(path)), zipfile.ZipFile(str(out))
    for name in a.namelist():
        if name != "Metadata/project_settings.config":
            assert a.read(name) == b.read(name), name
    new = json.loads(b.read("Metadata/project_settings.config"))
    changed = {k for k in new if new[k] != cfg.get(k)}
    assert changed <= {c["key"] for c in r["changes"]} | {"different_settings_to_system"}
    assert new["filament_settings_id"] == cfg["filament_settings_id"]
    with pytest.raises(ProjectError):
        engine.save(job, [], str(path))                           # never over the source


def test_multi_nozzle_target_is_refused(engine, tmp_path):
    v, t = box(10, 10, 10)
    stl = tmp_path / "k.stl"
    _write_stl(stl, v, t)
    job = engine.open(str(stl))
    with pytest.raises(ProjectError) as err:
        engine.prepare(job, "qidi|Acme D2 0.4 nozzle")
    assert err.value.code == "multi_nozzle_target"


def test_unsupported_file(engine, tmp_path):
    p = tmp_path / "a.step"
    p.write_text("x")
    with pytest.raises(ProjectError):
        engine.open(str(p))
