"""A tiny slicer profile library on disk (the layout Bambu Studio / QIDI Studio / OrcaSlicer use)."""

import json
import os

from fixtures import PROCESS, PLA


def _w(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)


def make_library(appdata, folder="QIDIStudio", vendor="Acme"):
    """%APPDATA%/<folder>/system/<vendor>.json + profiles. Two printers: a single-nozzle
    'Acme P1 0.4 nozzle' (220x200 bed) and a dual-nozzle 'Acme D2 0.4 nozzle'."""
    root = os.path.join(appdata, folder)
    system = os.path.join(root, "system")
    vdir = os.path.join(system, vendor)
    machines = {
        "fdm_machine_common": {"type": "machine", "name": "fdm_machine_common", "from": "system",
                               "instantiation": "false", "nozzle_diameter": ["0.4"], "printer_model": "",
                               "printable_area": ["0x0", "200x0", "200x200", "0x200"], "printable_height": "200",
                               "extruder_type": ["Direct Drive"], "default_nozzle_volume_type": ["Standard"],
                               "machine_start_gcode": "G28", "retraction_length": ["0.8"],
                               "max_layer_height": ["0.28"], "min_layer_height": ["0.08"]},
        "Acme P1 0.4 nozzle": {"type": "machine", "name": "Acme P1 0.4 nozzle", "inherits": "fdm_machine_common",
                               "from": "system", "instantiation": "true", "printer_model": "Acme P1",
                               "printable_area": ["0x0", "220x0", "220x200", "0x200"], "printable_height": "180",
                               "default_print_profile": "0.20mm Standard @Acme P1",
                               "default_filament_profile": ["Acme PLA @P1"], "default_bed_type": "Textured PEI Plate"},
        "Acme D2 0.4 nozzle": {"type": "machine", "name": "Acme D2 0.4 nozzle", "inherits": "fdm_machine_common",
                               "from": "system", "instantiation": "true", "printer_model": "Acme D2",
                               "nozzle_diameter": ["0.4", "0.4"]},
    }
    process_common = dict(PROCESS, type="process", name="fdm_process_common", **{"from": "system"})
    process_common["instantiation"] = "false"
    processes = {
        "fdm_process_common": process_common,
        "0.20mm Standard @Acme P1": {"type": "process", "name": "0.20mm Standard @Acme P1", "inherits": "fdm_process_common",
                                    "from": "system", "instantiation": "true", "layer_height": "0.2",
                                    "outer_wall_speed": ["150"], "compatible_printers": ["Acme P1 0.4 nozzle"]},
        "0.12mm Fine @Acme P1": {"type": "process", "name": "0.12mm Fine @Acme P1", "inherits": "fdm_process_common",
                                 "from": "system", "instantiation": "true", "layer_height": "0.12",
                                 "compatible_printers_condition": "printer_model==\"Acme P1\" and nozzle_diameter[0]==0.4"},
    }
    fil_common = {k: [v] for k, v in PLA.items()}
    fil_common.update({"type": "filament", "name": "fdm_filament_common", "from": "system", "instantiation": "false",
                       "filament_extruder_variant": ["Direct Drive Standard", "Direct Drive High Flow"],
                       "nozzle_temperature": ["215", "230"], "filament_shrink": ["100%"],
                       "default_filament_colour": [""]})
    filaments = {
        "fdm_filament_common": fil_common,
        "Acme PLA @P1": {"type": "filament", "name": "Acme PLA @P1", "inherits": "fdm_filament_common",
                         "from": "system", "instantiation": "true", "filament_type": ["PLA"],
                         "filament_vendor": ["Acme"], "filament_id": "AP01",
                         "compatible_printers": ["Acme P1 0.4 nozzle"]},
        "Generic PETG @P1": {"type": "filament", "name": "Generic PETG @P1", "inherits": "fdm_filament_common",
                             "from": "system", "instantiation": "true", "filament_type": ["PETG"],
                             "filament_vendor": ["Generic"], "nozzle_temperature": ["240", "250"],
                             "fan_max_speed": ["60"], "compatible_printers": ["Acme P1 0.4 nozzle"]},
        "Acme PA-CF @P1": {"type": "filament", "name": "Acme PA-CF @P1", "inherits": "fdm_filament_common",
                           "from": "system", "instantiation": "true", "filament_type": ["PA-CF"],
                           "filament_vendor": ["Acme"], "nozzle_temperature": ["280", "290"],
                           "compatible_printers": ["Acme P1 0.4 nozzle"]},
        "Other PLA @X": {"type": "filament", "name": "Other PLA @X", "inherits": "fdm_filament_common",
                         "from": "system", "instantiation": "true", "filament_type": ["PLA"],
                         "compatible_printers": ["Someone Else"]},
    }
    index = {"name": vendor, "version": "02.07.00.01", "machine_model_list": [], "machine_list": [],
             "process_list": [], "filament_list": []}
    for kind, items, lst in (("machine", machines, "machine_list"), ("process", processes, "process_list"),
                             ("filament", filaments, "filament_list")):
        for name, data in items.items():
            sub = "%s/%s.json" % (kind, name)
            _w(os.path.join(vdir, sub), data)
            index[lst].append({"name": name, "sub_path": sub})
    _w(os.path.join(system, vendor + ".json"), index)
    # a user preset that only overrides one value per variant ("nil" keeps the inherited one)
    _w(os.path.join(root, "user", "default", "filament", "My PLA.json"),
       {"name": "My PLA", "inherits": "Acme PLA @P1", "from": "User", "nozzle_temperature": ["205", "nil"]})
    with open(os.path.join(root, folder + ".conf"), "w", encoding="utf-8") as fh:
        json.dump({"app": {"version": "02.07.00.01"},
                   "models": [{"model": "Acme P1", "nozzle_diameter": "0.4", "vendor": vendor},
                              {"model": "Acme D2", "nozzle_diameter": "0.4", "vendor": vendor}],
                   "filaments": ["Acme PLA @P1"]}, fh)
    return root
