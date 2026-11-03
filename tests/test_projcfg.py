from ayarci.projcfg import ProjectConfig
from ayarci.safety import validate


def h2c_like():
    """Two nozzles, two volume variants each, three filaments (shapes of a real Bambu Studio 2.5 H2C project)."""
    return {
        "filament_settings_id": ["PLA A", "PA B", "PLA C"],
        "filament_type": ["PLA", "PA", "PLA"],
        "filament_map": ["1", "1", "1"],
        "extruder_type": ["Direct Drive", "Direct Drive"],
        "nozzle_volume_type": ["Standard", "Standard"],
        "nozzle_diameter": ["0.4", "0.4"],
        "print_extruder_id": ["1", "1", "2", "2"],
        "print_extruder_variant": ["Direct Drive Standard", "Direct Drive High Flow"] * 2,
        "initial_layer_speed": ["50", "60", "20", "60"],
        "outer_wall_speed": ["200", "200", "200", "200"],
        "layer_height": "0.2",
        "filament_self_index": ["1", "1", "2", "2", "3", "3"],
        "filament_extruder_variant": ["Direct Drive Standard", "Direct Drive High Flow"] * 3,
        "nozzle_temperature": ["220", "230", "260", "270", "210", "215"],
        "filament_max_volumetric_speed": ["20", "30", "12", "16", "21", "29"],
        "fan_max_speed": ["100", "40", "90"],
        "nozzle_temperature_range_low": ["190", "240", "190"],
        "nozzle_temperature_range_high": ["240", "280", "240"],
        "different_settings_to_system": ["", "", "", "", ""],
        "curr_bed_type": "Textured PEI Plate",
    }


def test_values_follow_filament_and_extruder():
    cfg = h2c_like()
    pc = ProjectConfig(cfg, filament_index=2, filament_map=["1", "1", "2"])
    assert pc.extruder_of_filament() == 2
    assert pc.process_index() == 2
    assert pc.value("initial_layer_speed") == "20"
    assert pc.value("nozzle_temperature") == "210"        # slot 3, Standard variant
    assert pc.value("fan_max_speed") == "90"
    assert pc.printer_info()["nozzle_diameter"] == "0.4"


def test_apply_keeps_other_slots_and_scales_variants():
    cfg = h2c_like()
    pc = ProjectConfig(cfg, filament_index=0)
    ctx = pc.context()
    changes, rejected = validate([{"key": "nozzle_temperature", "value": 225, "reason": "x"},
                                  {"key": "initial_layer_speed", "value": 40, "reason": "x"},
                                  {"key": "fan_max_speed", "value": 80, "reason": "x"}], ctx)
    assert not rejected
    pc.apply(changes)
    # slot 1: Standard 220 -> 225, High Flow keeps its +10 offset; other slots untouched
    assert cfg["nozzle_temperature"] == ["225", "235", "260", "270", "210", "215"]
    # process anchor (extruder 1 Standard) 50 -> 40: every variant scaled by 0.8
    assert cfg["initial_layer_speed"] == ["40", "48", "16", "48"]
    assert cfg["fan_max_speed"] == ["80", "40", "90"]
    assert cfg["different_settings_to_system"][0] == "initial_layer_speed"
    assert cfg["different_settings_to_system"][1] == "fan_max_speed;nozzle_temperature"


def test_scalar_and_bool_values():
    cfg = {"filament_settings_id": ["PLA"], "enable_support": "0", "enable_overhang_speed": ["1", "1"],
           "sparse_infill_density": "15%"}
    pc = ProjectConfig(cfg)
    changes, _ = validate([{"key": "enable_support", "value": "1", "reason": ""},
                           {"key": "enable_overhang_speed", "value": False, "reason": ""},
                           {"key": "sparse_infill_density", "value": "25%", "reason": ""}], pc.context())
    pc.apply(changes)
    assert cfg["enable_support"] == "1"
    assert cfg["enable_overhang_speed"] == ["0", "0"]
    assert cfg["sparse_infill_density"] == "25%"


def test_flavor_specific_enums():
    cfg = {"filament_settings_id": ["PLA"], "enable_support": "1", "support_style": "default",
           "sparse_infill_pattern": "grid"}
    pc = ProjectConfig(cfg)
    ctx = pc.context()
    ctx["flavor"] = "bambu"
    changes, rejected = validate([{"key": "support_style", "value": "organic", "reason": ""},
                                  {"key": "sparse_infill_pattern", "value": "tpmsd", "reason": ""}], ctx)
    assert not changes and len(rejected) == 2          # Orca-only values refused for Bambu Studio
    changes, rejected = validate([{"key": "support_style", "value": "tree_organic", "reason": ""}], ctx)
    assert changes and changes[0]["new"] == "tree_organic"
    ctx["flavor"] = "orca"
    changes, _ = validate([{"key": "support_style", "value": "organic", "reason": ""}], ctx)
    assert changes[0]["new"] == "organic"
