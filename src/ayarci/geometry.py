"""3DsetuPia - model measurement (runs locally, the model itself never leaves the PC).

Input: a list of parts, each {"object": name, "vertices": (N,3), "triangles": (M,3),
"matrix": 4x4 world transform}. Output: plain-JSON facts used by the rule engine,
the AI prompt and the UI.
"""

import math

import numpy as np

AXIS_ALIGNED_COS = math.cos(math.radians(10.0))   # normal within 10 deg of an axis
FLAT_COS = math.cos(math.radians(8.0))             # face counts as horizontal


def _world_triangles(part):
    v = np.asarray(part["vertices"], dtype=np.float64)
    t = np.asarray(part["triangles"], dtype=np.int64)
    if v.size == 0 or t.size == 0:
        return np.zeros((0, 3, 3))
    m = part.get("matrix")
    if m is not None:
        m = np.asarray(m, dtype=np.float64)
        v = v @ m[:3, :3].T + m[:3, 3]
    if t.max(initial=-1) >= len(v) or t.min(initial=0) < 0:
        raise ValueError("mesh has out-of-range triangle indices")
    return v[t]


def _ray_thickness(tri, normals, areas, max_rays, rng):
    """Local wall thickness: shoot rays inward from sampled faces, measure the first hit."""
    m = len(tri)
    if m < 4:
        return []
    a = tri[:, 0]
    e1 = tri[:, 1] - a
    e2 = tri[:, 2] - a
    p = areas / areas.sum()
    count = int(min(max_rays, max(16, 6e7 // max(m, 1))))
    count = min(count, m)
    idx = rng.choice(m, size=count, replace=False, p=p)
    out = []
    for i in idx:
        n = normals[i]
        if not np.isfinite(n).all():
            continue
        d = -n
        o = tri[i].mean(axis=0) + d * 1e-4
        pvec = np.cross(d, e2)
        det = np.einsum("ij,ij->i", e1, pvec)
        ok = np.abs(det) > 1e-12
        inv = np.zeros_like(det)
        inv[ok] = 1.0 / det[ok]
        tvec = o - a
        u = np.einsum("ij,ij->i", tvec, pvec) * inv
        qvec = np.cross(tvec, e1)
        v = (qvec @ d) * inv
        t = np.einsum("ij,ij->i", e2, qvec) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-3)
        hit[i] = False
        if hit.any():
            out.append(float(t[hit].min()))
    return out


def analyze_object(name, parts, max_rays=96, seed=7):
    tris = [_world_triangles(p) for p in parts]
    tris = [t for t in tris if len(t)]
    if not tris:
        return None
    tri = np.concatenate(tris, axis=0)
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    norm = np.linalg.norm(cross, axis=1)
    good = norm > 1e-12
    tri, cross, norm = tri[good], cross[good], norm[good]
    if len(tri) == 0:
        return None
    areas = 0.5 * norm
    normals = cross / norm[:, None]
    nz = normals[:, 2]
    total_area = float(areas.sum())

    pts = tri.reshape(-1, 3)
    mn, mx = pts.min(axis=0), pts.max(axis=0)
    size = mx - mn
    zmin, zmax = float(mn[2]), float(mx[2])
    height = float(size[2])
    tri_zmin = tri[:, :, 2].min(axis=1)
    tri_zmax = tri[:, :, 2].max(axis=1)
    tri_zc = tri[:, :, 2].mean(axis=1)

    # Volume (closed meshes; abs for flipped orientation)
    volume = float(abs(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()) / 6.0)

    # Bed contact: downward flat faces sitting at z-min
    on_bed = (nz < -FLAT_COS) & (tri_zmax < zmin + 0.05)
    contact_area = float(areas[on_bed].sum())

    # Overhangs: downward faces above the first layer; slope measured from horizontal
    down = (nz < 0) & ~on_bed & (tri_zc > zmin + 0.3)
    slope = np.degrees(np.arccos(np.clip(-nz, -1.0, 1.0)))   # 0 = flat ceiling, 90 = vertical
    def _area(mask):
        return float(areas[mask].sum())
    overhang = {
        "below_30deg_mm2": round(_area(down & (slope < 30)), 1),
        "below_45deg_mm2": round(_area(down & (slope < 45)), 1),
        "flat_ceiling_mm2": round(_area(down & (slope < 8)), 1),
    }
    low_point_area = 0.0
    # rough "starts in mid-air" indicator: downward faces that are local lowest points
    if np.any(down & (slope < 30)):
        low_point_area = _area(down & (slope < 30) & (tri_zmax - tri_zmin < 0.5))
    overhang["isolated_low_points_mm2"] = round(low_point_area, 1)

    # Flat tops (ironing candidates)
    up_flat = nz > FLAT_COS
    topmost = up_flat & (tri_zmin > zmax - 0.15)
    top_flat_area = _area(up_flat)
    topmost_area = _area(topmost)

    # Shape character
    an = np.abs(normals)
    aligned = an.max(axis=1) > AXIS_ALIGNED_COS
    organic_score = 1.0 - (_area(aligned) / total_area if total_area else 0.0)
    tri_density = len(tri) / max(total_area, 1e-6)  # triangles per mm2

    footprint_x, footprint_y = float(size[0]), float(size[1])
    min_xy = max(min(footprint_x, footprint_y), 1e-6)
    slenderness = height / min_xy                                  # geometric aspect ratio
    tipping = height / max(math.sqrt(max(contact_area, 0.0)), 1.0)  # height vs real bed contact

    rng = np.random.default_rng(seed)
    thick = sorted(_ray_thickness(tri, normals, areas, max_rays, rng))

    def pct(q):
        if not thick:
            return None
        k = min(len(thick) - 1, max(0, int(round(q * (len(thick) - 1)))))
        return round(thick[k], 2)

    return {
        "name": name,
        "triangles": int(len(tri)),
        "size_mm": [round(float(s), 1) for s in size],
        "height_mm": round(height, 1),
        "volume_cm3": round(volume / 1000.0, 2),
        "surface_cm2": round(total_area / 100.0, 1),
        "bed_contact_mm2": round(contact_area, 1),
        "slenderness": round(slenderness, 2),
        "tipping_index": round(tipping, 2),
        "overhang": overhang,
        "overhang_ratio": round(overhang["below_30deg_mm2"] / total_area, 4) if total_area else 0.0,
        "flat_top_mm2": round(top_flat_area, 1),
        "topmost_flat_mm2": round(topmost_area, 1),
        "organic_score": round(float(organic_score), 2),
        "triangle_density": round(float(tri_density), 3),
        "wall_thickness_mm": {"p05": pct(0.05), "p10": pct(0.10), "median": pct(0.5),
                              "samples": len(thick)},
    }


def classify(obj):
    """Human-friendly shape tags derived from the numbers (used by rules and the UI)."""
    tags = []
    if obj is None:
        return tags
    h = obj["height_mm"]
    size = obj["size_mm"]
    if obj["slenderness"] >= 3.0 and h >= 30:
        tags.append("tall_thin")
    if obj["bed_contact_mm2"] < 80 and h >= 10:
        tags.append("small_base")
    if obj["tipping_index"] >= 6.0 and h >= 25:
        tags.append("tipping_risk")
    if max(size[0], size[1]) >= 150 or obj["bed_contact_mm2"] >= 8000:
        tags.append("large_footprint")
    if obj["organic_score"] >= 0.45:
        tags.append("organic")
    elif obj["organic_score"] <= 0.2:
        tags.append("mechanical")
    if max(size) <= 30:
        tags.append("small")
    p10 = obj["wall_thickness_mm"]["p10"]
    if p10 is not None and p10 < 1.2:
        tags.append("thin_features")
    ov = obj["overhang"]["below_30deg_mm2"]
    if ov >= max(25.0, 0.004 * obj["surface_cm2"] * 100):
        tags.append("needs_support")
    elif ov < 5.0:
        tags.append("self_supporting")
    if obj["topmost_flat_mm2"] >= 300:
        tags.append("flat_top")
    return tags


def analyze_plate(parts, max_rays=96):
    """parts: list of dicts with object, vertices, triangles, matrix."""
    by_obj = {}
    order = []
    for p in parts:
        key = p.get("object") or "object"
        if key not in by_obj:
            by_obj[key] = []
            order.append(key)
        by_obj[key].append(p)
    objects = []
    for name in order:
        res = analyze_object(name, by_obj[name], max_rays=max_rays)
        if res is not None:
            res["tags"] = classify(res)
            objects.append(res)
    if not objects:
        return {"objects": [], "summary": {}}
    def worst(key, fn=max):
        return fn(o[key] for o in objects)
    thick = [o["wall_thickness_mm"]["p10"] for o in objects if o["wall_thickness_mm"]["p10"]]
    tags = sorted({t for o in objects for t in o["tags"]})
    summary = {
        "object_count": len(objects),
        "max_height_mm": worst("height_mm"),
        "max_slenderness": worst("slenderness"),
        "max_tipping_index": worst("tipping_index"),
        "min_bed_contact_mm2": worst("bed_contact_mm2", min),
        "total_overhang_below_30deg_mm2": round(sum(o["overhang"]["below_30deg_mm2"] for o in objects), 1),
        "max_overhang_ratio": worst("overhang_ratio"),
        "max_topmost_flat_mm2": worst("topmost_flat_mm2"),
        "mean_organic_score": round(sum(o["organic_score"] for o in objects) / len(objects), 2),
        "min_wall_thickness_p10_mm": min(thick) if thick else None,
        "max_footprint_mm": max(max(o["size_mm"][0], o["size_mm"][1]) for o in objects),
        "min_object_size_mm": min(min(o["size_mm"]) for o in objects),
        "total_volume_cm3": round(sum(o["volume_cm3"] for o in objects), 2),
        "tags": tags,
    }
    return {"objects": objects, "summary": summary}
