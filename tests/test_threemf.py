import json
import zipfile

import numpy as np

from ayarci.threemf import Project, parse_transform, format_transform
from ayarci.meshfiles import build_project, read_stl, load_meshes
from ayarci.placement import relocate, plate_origin, columns, layout_new
from meshes import box


def _cfg(n=2):
    return {"filament_settings_id": ["PLA %d" % i for i in range(n)], "filament_colour": ["#FFFFFF"] * n,
            "printer_settings_id": "Acme P1 0.4 nozzle", "printable_area": ["0x0", "200x0", "200x200", "0x200"],
            "layer_height": "0.2", "wall_loops": "2"}


def _project(tmp_path, meshes, positions, app="QIDIStudio-02.07.00.01"):
    p = build_project(meshes, _cfg(), app, positions)
    path = str(tmp_path / "src.3mf")
    p.write(path)
    return Project.load(path), path


def test_transform_round_trip():
    text = "1 0 0 0 -2.22044605e-16 1 0 -1 -2.22044605e-16 163.826236 160.940306 35"
    m = parse_transform(text)
    assert np.allclose(m @ [0, 0, 10, 1], [163.826236, 160.940306 - 10, 35, 1], atol=1e-6)
    assert np.allclose(parse_transform(format_transform(m)), m)


def test_build_load_measure_and_write(tmp_path):
    v, t = box(20, 10, 30)
    p, path = _project(tmp_path, [{"name": "Kutu", "vertices": v, "triangles": t}], [(100, 100)])
    assert p.kind == "project" and p.flavor == "qidi" and len(p.objects) == 1
    assert p.objects[0]["name"] == "Kutu" and p.main_filament() == 1
    lo, hi = p.item_bounds(p.items[0])
    assert np.allclose(lo, [90, 95, 0]) and np.allclose(hi, [110, 105, 30])
    parts = p.measure_parts()
    assert parts and parts[0]["triangles"].shape == (12, 3)
    # write: new settings, a move, a new application name; meshes stay byte-identical
    cfg = dict(p.settings, wall_loops="4")
    m = p.items[0]["transform"].copy()
    m[0, 3] += 5
    out = str(tmp_path / "out.3mf")
    p.write(out, settings=cfg, moves={0: m}, app="BambuStudio-02.08.00.01")
    q = Project.load(out)
    assert q.settings["wall_loops"] == "4" and q.flavor == "bambu"
    assert np.allclose(q.items[0]["transform"][:3, 3], m[:3, 3])
    a, b = zipfile.ZipFile(path), zipfile.ZipFile(out)
    assert a.namelist() == b.namelist()
    assert a.read("3D/Objects/object_1.model") == b.read("3D/Objects/object_1.model")


def test_sliced_project_is_saved_unsliced(tmp_path):
    v, t = box(10, 10, 10)
    p, path = _project(tmp_path, [{"name": "A", "vertices": v, "triangles": t}], [(50, 50)])
    sliced = str(tmp_path / "x.gcode.3mf")
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(sliced, "w") as dst:
        for n in src.namelist():
            dst.writestr(n, src.read(n))
        dst.writestr("Metadata/plate_1.gcode", "G1 X0\n")
        dst.writestr("Metadata/plate_1.gcode.md5", "abc")
    p = Project.load(sliced)
    assert p.sliced
    out = str(tmp_path / "y.3mf")
    p.write(out, settings=p.settings)
    names = zipfile.ZipFile(out).namelist()
    assert "Metadata/plate_1.gcode" not in names and "Metadata/plate_1.gcode.md5" not in names


def test_stl_binary_and_ascii(tmp_path):
    v, t = box(5, 6, 7)
    tri = v[t]
    data = bytearray(80) + len(tri).to_bytes(4, "little")
    for f in tri:
        data += np.zeros(3, np.float32).tobytes() + f.astype(np.float32).tobytes() + b"\0\0"
    (tmp_path / "b.stl").write_bytes(bytes(data))
    vb, tb = read_stl(str(tmp_path / "b.stl"))
    assert len(vb) == 8 and len(tb) == 12
    lines = ["solid x"]
    for f in tri:
        lines += ["facet normal 0 0 0", "outer loop"] + ["vertex %g %g %g" % tuple(p) for p in f] + ["endloop", "endfacet"]
    (tmp_path / "a.stl").write_text("\n".join(lines + ["endsolid x"]))
    meshes = load_meshes(str(tmp_path / "a.stl"))
    assert meshes[0]["name"] == "a.stl" and len(meshes[0]["vertices"]) == 8


def test_plate_grid():
    assert [columns(n) for n in (1, 2, 3, 4, 5, 9, 10)] == [1, 2, 2, 2, 3, 3, 4]
    assert np.allclose(plate_origin(3, 4, 100, 50), [120, -60, 0])


def test_relocate_centres_and_packs(tmp_path):
    v1, t1 = box(40, 40, 20)
    v2, t2 = box(40, 40, 60)
    p, _ = _project(tmp_path, [{"name": "A", "vertices": v1, "triangles": t1},
                               {"name": "B", "vertices": v2, "triangles": t2}], [(60, 100), (140, 100)])
    # bigger bed: arrangement kept, centred
    moves, report = relocate(p, [0, 0, 200, 200], [0, 0, 300, 300], 250)
    assert report[0]["status"] == "moved" and not report[0]["too_tall"]
    xs = sorted(m[0, 3] for m in moves.values())
    assert np.allclose(xs, [110, 190])
    # narrower bed: re-packed in rows; too short for B
    moves, report = relocate(p, [0, 0, 200, 200], [0, 0, 100, 120], 50)
    assert report[0]["status"] == "packed" and report[0]["too_tall"] == ["B"]
    # an object larger than the bed is reported, never scaled
    moves, report = relocate(p, [0, 0, 200, 200], [0, 0, 30, 30], 250)
    assert report[0]["status"] == "too_big" and set(report[0]["too_big"]) == {"A", "B"}


def test_layout_new_centres_meshes():
    v, t = box(20, 20, 20)
    pos, fits = layout_new([{"vertices": v}], [0, 0, 220, 200])
    assert fits and np.allclose(pos[0], (110, 100))
    pos, fits = layout_new([{"vertices": v * 20}], [0, 0, 220, 200])
    assert not fits
