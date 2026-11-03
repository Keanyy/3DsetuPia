import meshes as M
from ayarci import geometry as g, rules, safety
from fixtures import ctx, PETG, ABS, PROCESS


def run(mesh, **kw):
    c = ctx(**kw)
    an = g.analyze_plate([M.part("x", mesh)])
    ch, rej = safety.validate(rules.propose(an, c), c)
    return {x["key"]: x for x in ch}, rej, c


MUSHROOM = M.merge(M.cylinder(3, 30), M.cylinder(25, 5, oz=30))


def test_support_enabled_for_mushroom():
    ch, rej, _ = run(MUSHROOM)
    assert ch["enable_support"]["new"] == "1"
    assert not rej


def test_support_disabled_when_not_needed():
    proc = dict(PROCESS, enable_support="1")
    ch, _, _ = run(M.box(20, 20, 20), process=proc)
    assert ch["enable_support"]["new"] == "0"
    # support sub-settings must not be proposed when support ends up off
    assert not any(k.startswith("support_") for k in ch)


def test_tall_tower_gets_brim_and_walls():
    ch, _, _ = run(M.cylinder(4, 120))
    assert ch["brim_type"]["new"] == "outer_only"
    assert int(ch["wall_loops"]["new"]) >= 3


def test_looks_intent_thin_layers_and_ironing():
    ch, _, _ = run(M.box(40, 40, 10), intent="looks")
    assert float(ch["layer_height"]["new"]) <= 0.16
    assert ch["ironing_type"]["new"] == "top"


def test_speed_intent():
    ch, _, _ = run(M.box(40, 40, 40), intent="speed")
    assert float(ch["layer_height"]["new"]) >= 0.24
    assert ch["sparse_infill_density"]["new"] == "10%"


def test_strength_intent():
    ch, _, _ = run(M.box(40, 40, 40), intent="strength")
    assert int(ch["wall_loops"]["new"]) >= 5
    assert ch["sparse_infill_pattern"]["new"] == "gyroid"
    assert ch["sparse_infill_density"]["new"] == "40%"


def test_petg_fan_and_abs_brim():
    ch, _, _ = run(M.box(40, 40, 10), filament=PETG)
    assert float(ch["fan_max_speed"]["new"]) <= 60
    ch, _, _ = run(M.box(160, 120, 10), filament=ABS)
    assert ch["brim_type"]["new"] == "outer_only"
    assert float(ch["fan_max_speed"]["new"]) <= 40


def test_safety_rejects_and_clamps():
    c = ctx(filament=PETG)
    props = [
        {"key": "machine_start_gcode", "value": "G28"},
        {"key": "filament_colour", "value": "#FF0000"},
        {"key": "hot_plate_temp", "value": "60"},          # not the active plate
        {"key": "layer_height", "value": "0.9"},            # nozzle 0.4 -> clamp 0.28 (printer max)
        {"key": "nozzle_temperature", "value": "300"},      # PETG range 220..260
        {"key": "outer_wall_speed", "value": "900"},        # max +30 %
        {"key": "support_type", "value": "TREE(AUTO)"},     # case-insensitive enum
        {"key": "brim_type", "value": "painted"},           # not offered
        {"key": "wall_loops", "value": "abc"},
        {"key": "filament_max_volumetric_speed", "value": "30"},  # decrease only
    ]
    ch, rej = safety.validate(props, c, "ai")
    got = {x["key"]: x["new"] for x in ch}
    assert got["layer_height"] == "0.28"
    assert got["nozzle_temperature"] == "260"
    assert got["outer_wall_speed"] == "260"
    assert "support_type" not in got           # support stays off -> sub-setting dropped
    assert "filament_max_volumetric_speed" not in got   # clamped to current -> no change
    rejected = {r["key"] for r in rej}
    assert {"machine_start_gcode", "filament_colour", "hot_plate_temp", "brim_type", "wall_loops"} <= rejected


def test_vector_values_keep_their_shape():
    c = ctx()
    c["current"]["outer_wall_speed"] = "200,200"
    c["current"]["enable_overhang_speed"] = "1,1"
    ch, _ = safety.validate([{"key": "outer_wall_speed", "value": 150},
                             {"key": "enable_overhang_speed", "value": False}], c)
    got = {x["key"]: x["new"] for x in ch}
    assert got["outer_wall_speed"] == "150,150"
    assert got["enable_overhang_speed"] == "0,0"


def test_no_op_changes_are_dropped():
    c = ctx()
    ch, _ = safety.validate([{"key": "layer_height", "value": "0.20"},
                             {"key": "sparse_infill_density", "value": "15"}], c)
    assert ch == []


def test_english_reasons():
    ch, _, _ = run(MUSHROOM, lang="en")
    assert "overhang" in ch["enable_support"]["reason"].lower()
