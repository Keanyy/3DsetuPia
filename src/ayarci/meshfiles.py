"""3DsetuPia - plain model files (STL, OBJ, settings-free 3MF) and building a new project from them.

The new project uses the same 3MF layout Bambu Studio / QIDI Studio / OrcaSlicer
write themselves, so the slicer opens it as one of its own projects.
"""

import io
import json
import os
import re
import struct
import uuid
import zipfile

import numpy as np

from .threemf import Project, format_transform, ProjectError, SETTINGS_ENTRY  # bundle:strip

MESH_EXTENSIONS = (".stl", ".obj")


def _weld(tri_vertices):
    """(M,3,3) triangle corners -> shared vertices (N,3) + indices (M,3)."""
    flat = np.asarray(tri_vertices, dtype=np.float32).reshape(-1, 3)
    if not len(flat):
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int32)
    uniq, inv = np.unique(flat, axis=0, return_inverse=True)
    return uniq.astype(np.float32), inv.reshape(-1, 3).astype(np.int32)


def read_stl(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) >= 84:
        count = struct.unpack("<I", data[80:84])[0]
        if 84 + count * 50 == len(data):
            rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]),
                                count=count, offset=84)
            return _weld(rec["v"])
    text = data.decode("ascii", "ignore")
    nums = re.findall(r"vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", text)
    if not nums or len(nums) % 3:
        raise ProjectError("bad_mesh", os.path.basename(path))
    return _weld(np.array(nums, dtype=np.float32).reshape(-1, 3, 3))


def read_obj(path):
    verts, faces = [], []
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.startswith("v "):
                p = line.split()
                verts.append([float(p[1]), float(p[2]), float(p[3])])
            elif line.startswith("f "):
                idx = [int(tok.split("/")[0]) for tok in line.split()[1:]]
                idx = [i - 1 if i > 0 else len(verts) + i for i in idx]
                for k in range(1, len(idx) - 1):        # fan-triangulate polygons
                    faces.append([idx[0], idx[k], idx[k + 1]])
    if not verts or not faces:
        raise ProjectError("bad_mesh", os.path.basename(path))
    return np.array(verts, dtype=np.float32), np.array(faces, dtype=np.int32)


def load_meshes(path):
    """A mesh file -> [{"name", "vertices", "triangles"}] in world coordinates."""
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    if ext == ".stl":
        v, t = read_stl(path)
    elif ext == ".obj":
        v, t = read_obj(path)
    else:
        raise ProjectError("unsupported", ext)
    if not len(t):
        raise ProjectError("bad_mesh", name)
    return [{"name": name, "vertices": v, "triangles": t}]


def meshes_from_project(project):
    """World-space meshes of a 3MF that carries no slicer settings (e.g. exported from CAD)."""
    out = []
    for obj in project.objects:
        for item in [it for it in project.items if it["objectid"] == obj["id"] and it["printable"]]:
            vs, ts, off = [], [], 0
            for p in project.object_parts(obj, item):
                v = np.asarray(p["vertices"], dtype=np.float64)
                m = np.asarray(p["matrix"])
                vs.append(v @ m[:3, :3].T + m[:3, 3])
                ts.append(np.asarray(p["triangles"]) + off)
                off += len(v)
            if vs:
                out.append({"name": obj["name"], "vertices": np.concatenate(vs).astype(np.float32),
                            "triangles": np.concatenate(ts).astype(np.int32)})
    if not out:
        raise ProjectError("no_model")
    return out


# ---------------------------------------------------------------------- new project

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
 <Default Extension="gcode" ContentType="text/x.gcode"/>
</Types>
"""
_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""
_NS = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
       'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
       'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p"')


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _uuid():
    return str(uuid.uuid4())


def _mesh_xml(v, t):
    vb = io.StringIO()
    for x, y, z in v:
        vb.write('     <vertex x="%.7g" y="%.7g" z="%.7g"/>\n' % (x, y, z))
    tb = io.StringIO()
    for a, b, c in t:
        tb.write('     <triangle v1="%d" v2="%d" v3="%d"/>\n' % (a, b, c))
    return ("   <mesh>\n    <vertices>\n" + vb.getvalue() + "    </vertices>\n    <triangles>\n"
            + tb.getvalue() + "    </triangles>\n   </mesh>\n")


def build_project(meshes, settings, app, positions, path=None):
    """meshes: [{"name","vertices","triangles"}] in world space; positions: [(x, y)] bed centre per mesh.

    Each mesh becomes one object whose own coordinates are centred on its bounding box, placed
    with its bottom on the bed (the way the slicers store their own objects).
    """
    entries = {}
    resources, build, rels, ms_objects, plate_inst = [], [], [], [], []
    for i, mesh in enumerate(meshes):
        v = np.asarray(mesh["vertices"], dtype=np.float64)
        t = np.asarray(mesh["triangles"], dtype=np.int64)
        lo, hi = v.min(axis=0), v.max(axis=0)
        centre = (lo + hi) / 2.0
        local = (v - centre).astype(np.float32)
        oid = 2 * i + 2
        fname = "3D/Objects/object_%d.model" % (i + 1)
        entries[fname] = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" %s>\n'
                          ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n'
                          '  <object id="1" p:UUID="%s" type="model">\n%s  </object>\n </resources>\n'
                          ' <build/>\n</model>\n' % (_NS, _uuid(), _mesh_xml(local, t)))
        rels.append(' <Relationship Target="/%s" Id="rel-%d" '
                    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>' % (fname, i + 1))
        resources.append('  <object id="%d" p:UUID="%s" type="model">\n   <components>\n'
                         '    <component p:path="/%s" objectid="1" p:UUID="%s" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
                         '   </components>\n  </object>' % (oid, _uuid(), fname, _uuid()))
        x, y = positions[i]
        m = np.eye(4)
        m[:3, 3] = [x, y, (hi[2] - lo[2]) / 2.0]
        build.append('  <item objectid="%d" p:UUID="%s" transform="%s" printable="1"/>'
                     % (oid, _uuid(), format_transform(m)))
        name = _esc(mesh["name"])
        ms_objects.append('  <object id="%d">\n    <metadata key="name" value="%s"/>\n'
                          '    <metadata key="extruder" value="1"/>\n    <metadata face_count="%d"/>\n'
                          '    <part id="1" subtype="normal_part">\n      <metadata key="name" value="%s"/>\n'
                          '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                          '    </part>\n  </object>' % (oid, name, len(t), name))
        plate_inst.append('    <model_instance>\n      <metadata key="object_id" value="%d"/>\n'
                          '      <metadata key="instance_id" value="0"/>\n    </model_instance>' % oid)
    fil_ids = settings.get("filament_settings_id")
    n_fil = len(fil_ids) if isinstance(fil_ids, list) and fil_ids else 1
    entries["3D/3dmodel.model"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" %s>\n'
                                   ' <metadata name="Application">%s</metadata>\n'
                                   ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
                                   ' <resources>\n%s\n </resources>\n <build p:UUID="%s">\n%s\n </build>\n</model>\n'
                                   % (_NS, _esc(app), "\n".join(resources), _uuid(), "\n".join(build)))
    entries["3D/_rels/3dmodel.model.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships '
                                              'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                                              + "\n".join(rels) + "\n</Relationships>\n")
    entries["Metadata/model_settings.config"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + "\n".join(ms_objects) +
        '\n  <plate>\n    <metadata key="plater_id" value="1"/>\n    <metadata key="plater_name" value=""/>\n'
        '    <metadata key="locked" value="false"/>\n'
        '    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
        '    <metadata key="filament_maps" value="%s"/>\n' % " ".join(["1"] * n_fil) +
        "\n".join(plate_inst) + '\n  </plate>\n</config>\n')
    entries[SETTINGS_ENTRY] = json.dumps(settings, ensure_ascii=False, indent=4, sort_keys=True) + "\n"
    order = ["[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model", "3D/_rels/3dmodel.model.rels"]
    order += [k for k in entries if k.startswith("3D/Objects/")]
    order += [SETTINGS_ENTRY, "Metadata/model_settings.config"]
    entries["[Content_Types].xml"] = _CONTENT_TYPES
    entries["_rels/.rels"] = _ROOT_RELS
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in order:
            zf.writestr(name, entries[name])
    buf.seek(0)
    tmp = Project(path)
    with zipfile.ZipFile(buf) as zf:
        for info in zf.infolist():
            tmp.entries.append((info, zf.read(info.filename)))
    tmp._index()
    return tmp
