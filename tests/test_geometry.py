import numpy as np

import meshes as M
from ayarci import geometry as g


def tags(mesh):
    return set(g.analyze_plate([M.part("x", mesh)])["objects"][0]["tags"])


def test_cube_is_simple():
    t = tags(M.box(20, 20, 20))
    assert "self_supporting" in t and "mechanical" in t
    assert "needs_support" not in t and "tipping_risk" not in t


def test_tall_tower_tips():
    t = tags(M.cylinder(4, 120))
    assert {"tall_thin", "tipping_risk", "small_base"} <= t


def test_mushroom_needs_support():
    t = tags(M.merge(M.cylinder(3, 30), M.cylinder(25, 5, oz=30)))
    assert "needs_support" in t


def test_sphere_is_organic_and_needs_support():
    t = tags(M.sphere(25))
    assert "organic" in t and "needs_support" in t
    assert "tall_thin" not in t


def test_thin_wall_detected():
    o = g.analyze_plate([M.part("w", M.box(60, 0.8, 40))])["objects"][0]
    assert o["wall_thickness_mm"]["p10"] <= 0.81
    assert "thin_features" in o["tags"]


def test_transform_is_applied():
    m = np.eye(4)
    m[:3, :3] = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]   # lay the tower down (rotate about X)
    o = g.analyze_plate([M.part("t", M.cylinder(4, 120), m)])["objects"][0]
    assert o["height_mm"] < 10
    assert "tall_thin" not in o["tags"]


def test_volume_and_contact():
    o = g.analyze_plate([M.part("c", M.box(10, 20, 30))])["objects"][0]
    assert abs(o["volume_cm3"] - 6.0) < 0.01
    assert abs(o["bed_contact_mm2"] - 200.0) < 0.5


def test_multiple_objects_summary():
    r = g.analyze_plate([M.part("a", M.box(10, 10, 10)), M.part("b", M.cylinder(3, 90))])
    assert r["summary"]["object_count"] == 2
    assert "tall_thin" in r["summary"]["tags"]


def test_empty_and_degenerate():
    assert g.analyze_plate([])["objects"] == []
    v = np.zeros((3, 3), dtype=np.float32)
    t = np.array([[0, 1, 2]], dtype=np.int32)
    assert g.analyze_plate([{"object": "z", "vertices": v, "triangles": t, "matrix": np.eye(4)}])["objects"] == []


def test_big_mesh_is_fast():
    import time
    big = M.sphere(40, n=300)   # ~180k triangles
    t0 = time.time()
    g.analyze_plate([M.part("big", big)])
    assert time.time() - t0 < 20
