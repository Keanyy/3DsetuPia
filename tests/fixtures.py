"""Realistic preset values (serialized the way OrcaSlicer stores them)."""

PROCESS = {
    "layer_height": "0.2", "initial_layer_print_height": "0.2", "seam_position": "aligned",
    "seam_slope_type": "none", "wall_generator": "classic", "wall_sequence": "inner wall/outer wall",
    "precise_outer_wall": "0", "only_one_wall_top": "1", "detect_overhang_wall": "1", "thick_bridges": "0",
    "ironing_type": "no ironing", "ironing_pattern": "zig-zag", "ironing_flow": "10%",
    "ironing_spacing": "0.15", "ironing_speed": "30", "wall_loops": "2", "top_shell_layers": "5",
    "top_shell_thickness": "1", "bottom_shell_layers": "3", "bottom_shell_thickness": "0",
    "sparse_infill_density": "15%", "sparse_infill_pattern": "grid", "top_surface_pattern": "monotonicline",
    "bottom_surface_pattern": "monotonic", "internal_solid_infill_pattern": "monotonic",
    "ensure_vertical_shell_thickness": "ensure_all", "detect_thin_wall": "0", "infill_combination": "0",
    "initial_layer_speed": "50", "initial_layer_infill_speed": "105", "outer_wall_speed": "200",
    "inner_wall_speed": "300", "sparse_infill_speed": "270", "internal_solid_infill_speed": "250",
    "top_surface_speed": "200", "gap_infill_speed": "250", "bridge_speed": "50", "support_speed": "150",
    "support_interface_speed": "80", "default_acceleration": "10000", "outer_wall_acceleration": "5000",
    "inner_wall_acceleration": "0", "top_surface_acceleration": "2000", "initial_layer_acceleration": "500",
    "enable_overhang_speed": "1", "enable_support": "0", "support_type": "normal(auto)",
    "support_style": "default", "support_threshold_angle": "30", "support_on_build_plate_only": "0",
    "support_critical_regions_only": "0", "support_top_z_distance": "0.2", "support_bottom_z_distance": "0.2",
    "support_object_xy_distance": "0.35", "support_interface_top_layers": "2",
    "support_interface_bottom_layers": "2", "support_interface_spacing": "0.5",
    "support_base_pattern": "default", "support_base_pattern_spacing": "2.5", "raft_layers": "0",
    "tree_support_branch_angle": "45", "tree_support_branch_diameter": "2", "skirt_loops": "0",
    "skirt_distance": "2", "brim_type": "auto_brim", "brim_width": "5", "brim_object_gap": "0.1",
    "spiral_mode": "0",
}

PLA = {
    "filament_type": "PLA", "filament_vendor": "Bambu Lab", "nozzle_temperature": "220",
    "nozzle_temperature_initial_layer": "220", "nozzle_temperature_range_low": "190",
    "nozzle_temperature_range_high": "240", "fan_min_speed": "100", "fan_max_speed": "100",
    "overhang_fan_speed": "100", "close_fan_the_first_x_layers": "1", "slow_down_layer_time": "4",
    "filament_max_volumetric_speed": "21", "textured_plate_temp": "55",
    "textured_plate_temp_initial_layer": "55", "hot_plate_temp": "55", "hot_plate_temp_initial_layer": "55",
}

PETG = dict(PLA, filament_type="PETG", filament_vendor="Elegoo", nozzle_temperature="240",
            nozzle_temperature_initial_layer="240", nozzle_temperature_range_low="220",
            nozzle_temperature_range_high="260", fan_min_speed="40", fan_max_speed="90",
            overhang_fan_speed="90", textured_plate_temp="70", textured_plate_temp_initial_layer="70",
            filament_max_volumetric_speed="12")

ABS = dict(PLA, filament_type="ABS", nozzle_temperature="260", nozzle_temperature_initial_layer="260",
           nozzle_temperature_range_low="240", nozzle_temperature_range_high="280", fan_min_speed="10",
           fan_max_speed="80", textured_plate_temp="90", textured_plate_temp_initial_layer="90")

PRINTER = {"nozzle_diameter": "0.4", "printer_model": "Bambu Lab P1S", "printable_height": "250",
           "printer_structure": "corexy", "max_layer_height": "0.28", "min_layer_height": "0.08"}


def ctx(intent="balanced", filament=PLA, lang="tr", note="", process=None):
    cur = dict(process or PROCESS)
    cur.update({k: v for k, v in filament.items()})
    return {"lang": lang, "intent": intent, "note": note, "current": cur, "printer": dict(PRINTER),
            "filament": dict(filament), "bed_type": "Textured PEI Plate"}
