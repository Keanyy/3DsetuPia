"""Small mesh generators for tests (closed, outward-facing triangles)."""

import math

import numpy as np


def box(sx, sy, sz, ox=0.0, oy=0.0, oz=0.0):
    v = np.array([[0, 0, 0], [sx, 0, 0], [sx, sy, 0], [0, sy, 0],
                  [0, 0, sz], [sx, 0, sz], [sx, sy, sz], [0, sy, sz]], dtype=np.float32)
    v += np.array([ox, oy, oz], dtype=np.float32)
    t = np.array([[0, 2, 1], [0, 3, 2],        # bottom (-z)
                  [4, 5, 6], [4, 6, 7],        # top (+z)
                  [0, 1, 5], [0, 5, 4],        # -y
                  [1, 2, 6], [1, 6, 5],        # +x
                  [2, 3, 7], [2, 7, 6],        # +y
                  [3, 0, 4], [3, 4, 7]],       # -x
                 dtype=np.int32)
    return v, t


def merge(*meshes):
    vs, ts, off = [], [], 0
    for v, t in meshes:
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    return np.concatenate(vs), np.concatenate(ts)


def cylinder(r, h, n=48, oz=0.0):
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    ring = np.stack([r * np.cos(ang), r * np.sin(ang)], axis=1)
    bottom = np.column_stack([ring, np.full(n, oz)])
    top = np.column_stack([ring, np.full(n, oz + h)])
    v = np.vstack([bottom, top, [[0, 0, oz]], [[0, 0, oz + h]]]).astype(np.float32)
    cb, ct = 2 * n, 2 * n + 1
    t = []
    for i in range(n):
        j = (i + 1) % n
        t.append([i, j, n + j])
        t.append([i, n + j, n + i])
        t.append([cb, j, i])
        t.append([ct, n + i, n + j])
    return v, np.array(t, dtype=np.int32)


def sphere(r, n=32, oz=None):
    oz = r if oz is None else oz
    verts = [[0, 0, oz + r]]
    for i in range(1, n):
        th = math.pi * i / n
        for j in range(2 * n):
            ph = 2 * math.pi * j / (2 * n)
            verts.append([r * math.sin(th) * math.cos(ph), r * math.sin(th) * math.sin(ph),
                          oz + r * math.cos(th)])
    verts.append([0, 0, oz - r])
    v = np.array(verts, dtype=np.float32)
    m = 2 * n
    t = []
    for j in range(m):
        t.append([0, 1 + j, 1 + (j + 1) % m])
    for i in range(n - 2):
        for j in range(m):
            a = 1 + i * m + j
            b = 1 + i * m + (j + 1) % m
            c = 1 + (i + 1) * m + j
            d = 1 + (i + 1) * m + (j + 1) % m
            t.append([a, c, b])
            t.append([b, c, d])
    last = len(v) - 1
    base = 1 + (n - 2) * m
    for j in range(m):
        t.append([last, base + (j + 1) % m, base + j])
    return v, np.array(t, dtype=np.int32)


def part(name, mesh, matrix=None):
    v, t = mesh
    return {"object": name, "vertices": v, "triangles": t,
            "matrix": np.eye(4) if matrix is None else matrix}
