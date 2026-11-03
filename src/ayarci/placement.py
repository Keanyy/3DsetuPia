"""3DsetuPia - putting the objects of a project onto another printer's bed.

Bambu Studio, QIDI Studio and OrcaSlicer lay the plates of a project out in a
grid: plate i sits at (col * width * 1.2, -row * depth * 1.2). Objects keep
their arrangement on each plate; the group is centred on the new bed. When the
group is wider than the new bed the objects are re-packed in rows, and anything
that still does not fit is reported (never scaled).
"""

import math

import numpy as np

PLATE_GAP = 0.2          # LOGICAL_PART_PLATE_GAP in the slicers
MARGIN = 5.0             # mm kept free around objects when packing
SPACING = 6.0


def columns(count):
    v = math.sqrt(max(1, count))
    r = round(v)
    return int(r + 1 if v > r else r)


def plate_origin(index0, count, width, depth):
    cols = columns(count)
    row, col = divmod(index0, cols)
    return np.array([col * width * (1.0 + PLATE_GAP), -row * depth * (1.0 + PLATE_GAP), 0.0])


def _pack(sizes, bed_w, bed_d):
    """Shelf packing of (w, d) footprints inside the bed. -> list of (x, y) centres or None."""
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])
    x = y = MARGIN
    shelf = 0.0
    pos = [None] * len(sizes)
    for i in order:
        w, d = sizes[i]
        if w > bed_w - 2 * MARGIN or d > bed_d - 2 * MARGIN:
            return None
        if x + w > bed_w - MARGIN:
            x = MARGIN
            y += shelf + SPACING
            shelf = 0.0
        if y + d > bed_d - MARGIN:
            return None
        pos[i] = (x + w / 2.0, y + d / 2.0)
        x += w + SPACING
        shelf = max(shelf, d)
    return pos


def relocate(project, src_rect, dst_rect, dst_height):
    """Moves for project.write(): {build item position: new 4x4 transform} and a report per plate.

    src_rect / dst_rect: [xmin, ymin, xmax, ymax] of the printable area.
    """
    sw, sd = src_rect[2] - src_rect[0], src_rect[3] - src_rect[1]
    dw, dd = dst_rect[2] - dst_rect[0], dst_rect[3] - dst_rect[1]
    n_plates = len(project.plates)
    plate_index = {pl["id"]: i for i, pl in enumerate(project.plates)}
    moves, report = {}, []
    for pl in project.plates:
        idx = plate_index[pl["id"]]
        so = plate_origin(idx, n_plates, sw, sd)
        do = plate_origin(idx, n_plates, dw, dd)
        members = [(pos, it) for pos, it in enumerate(project.items) if it["plate"] == pl["id"]]
        boxes = []
        for pos, it in members:
            b = project.item_bounds(it)
            if b is not None:
                boxes.append((pos, it, b))
        if not boxes:
            continue
        lo = np.min([b[2][0] for b in boxes], axis=0)
        hi = np.max([b[2][1] for b in boxes], axis=0)
        names = [next((o["name"] for o in project.objects if o["id"] == it["objectid"]), "?")
                 for _, it, _ in boxes]
        too_tall = [names[k] for k, (_, _, b) in enumerate(boxes) if dst_height and b[1][2] - b[0][2] > dst_height + 0.01]
        group = hi - lo
        entry = {"plate": pl["id"], "objects": len(boxes), "too_tall": too_tall, "status": "moved",
                 "too_big": []}
        if group[0] <= dw - 2 and group[1] <= dd - 2:
            # keep the arrangement, centre it on the new bed
            centre_src = (lo + hi) / 2.0
            target = do + np.array([dst_rect[0] + dw / 2.0, dst_rect[1] + dd / 2.0, 0.0])
            shift = target - centre_src
            shift[2] = 0.0
            for pos, it, _ in boxes:
                m = np.array(it["transform"], dtype=np.float64)
                m[:3, 3] += shift
                moves[pos] = m
        else:
            sizes = [(b[1][0] - b[0][0], b[1][1] - b[0][1]) for _, _, b in boxes]
            centres = _pack(sizes, dw, dd)
            if centres is None:
                entry["status"] = "too_big"
                entry["too_big"] = [names[k] for k, s in enumerate(sizes)
                                    if s[0] > dw - 2 * MARGIN or s[1] > dd - 2 * MARGIN]
                if not entry["too_big"]:
                    entry["status"] = "crowded"
                # still bring the plate to the new bed so the slicer's Arrange (A) can finish the job
                centre_src = (lo + hi) / 2.0
                target = do + np.array([dst_rect[0] + dw / 2.0, dst_rect[1] + dd / 2.0, 0.0])
                shift = target - centre_src
                shift[2] = 0.0
                for pos, it, _ in boxes:
                    m = np.array(it["transform"], dtype=np.float64)
                    m[:3, 3] += shift
                    moves[pos] = m
            else:
                entry["status"] = "packed"
                for (pos, it, b), (cx, cy) in zip(boxes, centres):
                    m = np.array(it["transform"], dtype=np.float64)
                    box_centre = (b[0] + b[1]) / 2.0
                    want = do + np.array([dst_rect[0] + cx, dst_rect[1] + cy, 0.0])
                    m[0, 3] += want[0] - box_centre[0]
                    m[1, 3] += want[1] - box_centre[1]
                    moves[pos] = m
        report.append(entry)
    return moves, report


def layout_new(meshes, dst_rect):
    """Bed positions (x, y centres) for fresh meshes; fits=False if they cannot all fit."""
    dw, dd = dst_rect[2] - dst_rect[0], dst_rect[3] - dst_rect[1]
    sizes = []
    for m in meshes:
        v = np.asarray(m["vertices"])
        sizes.append((float(v[:, 0].max() - v[:, 0].min()), float(v[:, 1].max() - v[:, 1].min())))
    if len(sizes) == 1:
        return [(dst_rect[0] + dw / 2.0, dst_rect[1] + dd / 2.0)], sizes[0][0] <= dw and sizes[0][1] <= dd
    centres = _pack(sizes, dw, dd)
    if centres is None:
        return [(dst_rect[0] + dw / 2.0, dst_rect[1] + dd / 2.0)] * len(sizes), False
    # centre the packed block
    xs = [c[0] for c in centres]
    ys = [c[1] for c in centres]
    minx = min(c[0] - s[0] / 2 for c, s in zip(centres, sizes))
    maxx = max(c[0] + s[0] / 2 for c, s in zip(centres, sizes))
    miny = min(c[1] - s[1] / 2 for c, s in zip(centres, sizes))
    maxy = max(c[1] + s[1] / 2 for c, s in zip(centres, sizes))
    dx = (dw - (maxx - minx)) / 2.0 - minx
    dy = (dd - (maxy - miny)) / 2.0 - miny
    return [(dst_rect[0] + x + dx, dst_rect[1] + y + dy) for x, y in zip(xs, ys)], True
