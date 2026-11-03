import pytest

from ayarci.profiles import discover, Library, eval_condition
from profilelib import make_library


@pytest.fixture
def lib(tmp_path):
    make_library(str(tmp_path))
    found = discover(str(tmp_path))
    assert [s["id"] for s in found] == ["qidi"]
    assert found[0]["version"] == "02.07.00.01"
    return Library(found[0], str(tmp_path / "cache"))


def test_printers_resolve_inheritance(lib):
    printers = {p["name"]: p for p in lib.printers()}
    assert set(printers) == {"Acme P1 0.4 nozzle", "Acme D2 0.4 nozzle"}
    p1 = printers["Acme P1 0.4 nozzle"]
    assert p1["bed"] == [0, 0, 220, 200] and p1["height"] == 180 and p1["extruders"] == 1
    assert printers["Acme D2 0.4 nozzle"]["extruders"] == 2
    assert lib.machine("Acme P1 0.4 nozzle")["machine_start_gcode"] == "G28"     # from the parent


def test_compatibility_lists_and_conditions(lib):
    names = {p["name"] for p in lib.processes("Acme P1 0.4 nozzle")}
    assert names == {"0.20mm Standard @Acme P1", "0.12mm Fine @Acme P1"}       # list + condition
    assert {p["name"] for p in lib.processes("Acme D2 0.4 nozzle")} == set()
    fils = {f["name"] for f in lib.filaments("Acme P1 0.4 nozzle")}
    assert "Other PLA @X" not in fils and {"Acme PLA @P1", "My PLA", "Generic PETG @P1"} <= fils
    # the cache makes the second library start from disk facts
    lib.save_cache()
    again = Library(lib.slicer, lib._cache_path.rsplit("\\", 1)[0].rsplit("/", 1)[0])
    assert {f["name"] for f in again.filaments("Acme P1 0.4 nozzle")} == fils


def test_condition_evaluator():
    cfg = {"printer_model": "Acme P1", "nozzle_diameter": ["0.4", "0.6"], "printer_notes": "VENDOR_ACME fast"}
    assert eval_condition('printer_model=="Acme P1" and nozzle_diameter[0]==0.4', cfg)
    assert not eval_condition('nozzle_diameter[1]==0.4', cfg)
    assert eval_condition('printer_notes=~/.*VENDOR_ACME.*/ and not (printer_model=="X")', cfg)
    assert eval_condition("this is ??? not parseable", cfg)            # unknown syntax -> allowed


def test_picking_profiles(lib):
    m = "Acme P1 0.4 nozzle"
    assert lib.pick_process(m, 0.2) == "0.20mm Standard @Acme P1"
    assert lib.pick_process(m, 0.12) == "0.12mm Fine @Acme P1"
    assert lib.pick_filament(m, "PLA", "Acme", "Acme PLA @H2C") == "Acme PLA @P1"   # same product name
    assert lib.pick_filament(m, "PETG", "Elegoo", "x") == "Generic PETG @P1"
    assert lib.pick_filament(m, "PA", "Generic", "Generic PA") == "Acme PA-CF @P1"   # same family
    assert lib.pick_filament(m, "TPU", "", "") == "Acme PLA @P1"                    # printer default


def test_user_preset_nil_keeps_inherited_variant(lib):
    f = lib.resolve("My PLA", "filament")
    assert f["nozzle_temperature"] == ["205", "230"]
    assert f["filament_type"] == ["PLA"]


def test_build_config_single_nozzle(lib):
    source = {"filament_settings_id": ["a", "b"], "filament_colour": ["#FF0000", "#00FF00"],
              "filament_shrink": ["99%", "100%"], "curr_bed_type": "Cool Plate", "layer_height": "0.2",
              "some_new_filament_key": ["1", "2"], "flush_volumes_matrix": ["0", "100", "100", "0"]}
    cfg = lib.build_config("Acme P1 0.4 nozzle", "0.20mm Standard @Acme P1", ["Acme PLA @P1", "Generic PETG @P1"],
                           source=source, colours=source["filament_colour"])
    assert cfg["printer_settings_id"] == "Acme P1 0.4 nozzle"
    assert cfg["print_settings_id"] == "0.20mm Standard @Acme P1"
    assert cfg["filament_settings_id"] == ["Acme PLA @P1", "Generic PETG @P1"]
    # per-variant filament values collapse to the printer's own variant (Standard), one per filament
    assert cfg["nozzle_temperature"] == ["215", "240"]
    assert cfg["filament_extruder_variant"] == ["Direct Drive Standard"] * 2
    assert cfg["filament_self_index"] == ["1", "2"]
    assert cfg["fan_max_speed"][1] == "60"
    assert cfg["filament_colour"] == ["#FF0000", "#00FF00"]
    assert cfg["filament_shrink"] == ["100%", "100%"]                     # from the profiles
    assert cfg["some_new_filament_key"] == ["1", "2"]                     # kept from the source project
    assert cfg["flush_volumes_matrix"] == ["0", "100", "100", "0"]
    assert cfg["curr_bed_type"] == "Textured PEI Plate"                   # no Cool Plate temps on this printer
    assert cfg["outer_wall_speed"] == ["150"] and cfg["machine_start_gcode"] == "G28"
    assert cfg["different_settings_to_system"] == ["", "", "", ""]
    assert "compatible_printers" not in cfg and "inherits" not in cfg
