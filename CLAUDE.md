# CLAUDE.md – 3DsetuPia project hand-off

Read this first. It carries the context of the sessions that built the project.

## Maintainer and goal

- Maintainer: Kenan Çelik (GitHub `Keanyy`). Answer in Turkish, plain words; explain technical
  steps, cover the angles a non-specialist would not think of.
- Product: **3DsetuPia** (exact spelling; earlier names "Ayarcı", "3dSetuper"). The Python package
  and some file names stay `ayarci` internally (`src/ayarci`, `dist/ayarci.py`,
  `ayarci_settings.json`, `_ayarci.3mf` output suffix).
- Idea: users keep their own slicer; the program tunes the *many detailed settings*
  (quality/strength/speed/support/others/filament) for the model, with approval, without touching
  colours/painting. A general tool for every slicer that shares the Bambu/Orca 3MF format.
- Test printers: Bambu Lab H2C (dual nozzle) and QIDI Q2. Developed against Bambu Studio 02.08.02,
  QIDI Studio 02.07.02 and OrcaSlicer 2.4.2 on Windows 11, Python 3.14 (`py` launcher).
- Repository: https://github.com/Keanyy/3DsetuPia · site: https://keanyy.github.io/3DsetuPia/

## Status (2026-11-03)

Version 1.1.0, two deliverables sharing one core:

1. **Desktop program `3DsetuPia.exe`** (PyInstaller one-file, windowed, ~34 MB, Edge WebView2 UI via
   pywebview; `py tools/build_exe.py`). Opens 3MF project / settings-free 3MF / STL / OBJ →
   measures → rules or AI → safety filter → writes a NEW 3MF (`<name>_ayarci.3mf`). Same printer,
   or retarget to another single-nozzle printer from the installed slicers' vendor profiles, with
   bed re-placement.
2. **OrcaSlicer 2.5 plugin `dist/ayarci.py`** (not yet verified in a real Orca 2.5).

Verified:
- 63 pytest tests pass (`py -m pytest -q`).
- Real slicer CLIs sliced every output (`<exe> --slice 0 --outputdir <dir> <3mf>`, then
  `result.json` and the `; key = value` header of the G-code): H2C same-printer tune (values reach
  the G-code, other filament slots untouched), H2C→QIDI Q2 (centred on the 270 bed), H2C→Orca
  "Qidi Q2", H2C→Bambu X1C, a FreeCAD 3MF and an STL → Q2/X1C.
- The built exe: `--selftest` and `--uitest` (drives the real WebView2 page through the bridge,
  writes JSON) pass. Each running copy has its own WebView2 folder (`%TEMP%\3DsetuPia-webview\<pid>`);
  a shared folder let one copy's exit close another copy's window. Closing the window ends the process.

Open items:
- Multi-nozzle *targets* (retarget to H2D/H2C from another printer) are refused on purpose.
- Code signing (SmartScreen warning) — SignPath Foundation is an option.
- PrusaSlicer / Cura project formats are not supported.

## Facts established (3MF / slicers)

- Project settings: `Metadata/project_settings.config`, flat JSON, sorted keys, 4-space indent,
  CRLF from Windows slicers. Printer: `printer_settings_id`, `printer_model`, `printable_area`
  (`"0x0","330x0",...`), `printable_height`, `curr_bed_type`.
- Filament lists: one entry per slot; on Bambu 2.x some keys have one entry per slot *and* nozzle
  variant, `filament_self_index` says which slot owns each entry (list of 40 such keys in
  `profiles.VARIANT_FILAMENT_KEYS`). Process keys on H2C have 4 entries
  (`print_extruder_id` × `print_extruder_variant`). Plate-level `filament_maps` in
  `Metadata/model_settings.config` overrides the global `filament_map` (H2C sample: filament 6 → extruder 2).
- `Metadata/model_settings.config`: object `extruder`, part `subtype` (normal_part/modifier…),
  per-object setting overrides, plates with `model_instance`. Edit it at byte level only.
- Build items in `3D/3dmodel.model` carry 3MF row-vector transforms; plates are laid out in a
  grid with a 1.2 × bed stride (`placement.plate_origin`).
- Enum values verified against the slicer DLLs: "Rectilinear" is stored as `zig-zag`; organic
  support is `organic` (Orca) vs `tree_organic` (Bambu/QIDI); `ensure_vertical_shell_thickness` is
  `enabled` in Bambu/QIDI; `aligned_back`, `tpmsd`, `quartercubic`, `lateral-*` are Orca-only;
  `textured_cool_plate_temp` is Orca-only. See `catalog.py` `extra`.
- QIDI Studio fails to slice ("Failed slicing the model", rc -100) when a multi-filament project
  lacks a per-filament key such as `filament_shrink`; `profiles._fill_filament_keys_impl` fills
  them from the source project.
- Slicer CLIs' own retargeting (`--load-settings`/`--load-filaments` on a 3MF) does NOT apply
  filament presets reliably — that is why Ayarcı builds the config itself.
- Slicer profile libraries: `%APPDATA%\<Slicer>\system\<Vendor>.json` + `<Vendor>\{machine,process,filament}`;
  user presets in `user\<id>\<kind>\*.json` (values may be `"nil"` = inherit per variant);
  installed printers in `<Slicer>.conf` `"models"`. Opening ~1500 Bambu profile files takes ~25 s
  cold, so light facts are cached in `%APPDATA%\3DsetuPia\cache`.

## OrcaSlicer plugin facts (from SoftFever/OrcaSlicer source)

| Feature | 2.5.0-alpha | 2.5.0-beta | 2.5.0-rc |
|---|---|---|---|
| Python plugins, `orca.host.model()/preset_bundle()`, mesh access | yes | yes | yes |
| Preset write API `orca.host.preset.{process,filament}.begin_update()/set()/commit()` | **no** | yes | yes |
| Script `execute()` on a background worker | **no (UI thread)** | yes | yes |

Minimum 2.5.0-beta. `begin_update()` runs on the Script worker; edits stay unsaved. Orca Cloud
author/publish steps are unverified.

## Anthropic provider

Official `anthropic` SDK, default model `claude-opus-5-5`, `output_config` json_schema + effort
`high`, server-side fallback (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`),
retries without those on 400, checks `stop_reason == "refusal"`. Verified against the claude-api
skill and SDK 2.4.0 signatures on 2026-11-03.

## Conventions

- Edit `src/ayarci/*`; never edit `dist/ayarci.py` by hand (`py tools/build_plugin.py`). Relative
  imports end with `# bundle:strip`; no `import x as y` between project modules.
- Every user-facing string in Turkish and English (`ui.html`/`app.html` `T`, `i18n.py`).
- Safety model: whitelist in `catalog.py`, limits in `safety.py`; never add colour, painting,
  G-code, machine or post-processing keys to what the AI may change; never send the mesh to an AI.
  Retargeting copies the vendor's machine profile as is — the AI never edits machine keys.
- Never overwrite the user's source file; never commit API keys or `dist/*.exe`.
- After changing how configs are built or written, re-check with the real slicer CLIs.
- Bump `APP_VERSION` (app.py), `PLUGIN_VERSION` (plugin.py) and `CHANGELOG.md` for each release.
