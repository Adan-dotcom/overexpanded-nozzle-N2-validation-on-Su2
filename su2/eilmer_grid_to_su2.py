#!/usr/bin/env python3
"""Convert an Eilmer 5 structured multi-block grid (lmrsim/grid) to one SU2
mesh, merging the shared interface nodes, so SU2 runs on exactly the same grid.

Markers from the Eilmer bcTags:
  inflow -> INLET, wall -> WALL, shroud -> SHROUD, ambient -> FARFIELD,
  outflow_core / outflow_outer -> OUTLET, untagged faces on y=0 -> AXIS.
Untagged faces off the axis must be block-to-block interfaces (checked).

usage: eilmer_grid_to_su2.py LMRSIM_GRID_DIR OUT.su2
"""
import sys, os, gzip, json, glob
import numpy as np

gdir, out = sys.argv[1], sys.argv[2]
TAGMAP = {"inflow": "INLET", "wall": "WALL", "shroud": "SHROUD", "ambient": "FARFIELD",
          "outflow_core": "OUTLET", "outflow_outer": "OUTLET"}


def read_block(b):
    lines = gzip.open(os.path.join(gdir, f"grid-{b:04d}.gz"), "rt").read().split("\n")
    h, k = {}, 0
    while ":" in lines[k] or not lines[k][:1].isdigit():
        if ":" in lines[k]:
            a, v = lines[k].split(":", 1); h[a.strip()] = v.strip()
        k += 1
    ni, nj = int(h["niv"]), int(h["njv"])
    xyz = np.array([[float(v) for v in l.split()] for l in lines[k:k + ni * nj]])
    md = json.load(open(os.path.join(gdir, f"grid-{b:04d}.metadata")))
    return xyz[:, 0].reshape(nj, ni), xyz[:, 1].reshape(nj, ni), md


nblk = len(glob.glob(os.path.join(gdir, "grid-*.metadata")))
nodes, key2id = [], {}


def node_id(x, y):
    k = (round(x * 1e10), round(y * 1e10))      # 0.1 nm merge tolerance
    if k not in key2id:
        key2id[k] = len(nodes); nodes.append((x, y))
    return key2id[k]


quads, markers, faces_untagged, idmaps = [], {}, [], {}
for b in range(nblk):
    X, Y, md = read_block(b)
    nj, ni = X.shape
    ids = np.array([[node_id(X[j, i], Y[j, i]) for i in range(ni)] for j in range(nj)])
    idmaps[f"b{b}"] = ids                # SU2 PointID of Eilmer block vertex (j, i)
    for j in range(nj - 1):
        for i in range(ni - 1):
            quads.append((ids[j, i], ids[j, i + 1], ids[j + 1, i + 1], ids[j + 1, i]))  # CCW
    edges = {"south": ids[0, :], "north": ids[-1, :], "west": ids[:, 0], "east": ids[:, -1]}
    ys = {"south": Y[0, :], "north": Y[-1, :], "west": Y[:, 0], "east": Y[:, -1]}
    for side, tag in md["bcTags"].items():
        if side not in edges:          # e.g. Eilmer's "dummy_entry_without_trailing_comma"
            continue
        e = edges[side]
        if tag in TAGMAP:
            name = TAGMAP[tag]
        elif tag == "" and np.all(np.abs(ys[side]) < 1e-12):
            name = "AXIS"
        elif tag == "":
            faces_untagged.append((b, side, set(e.tolist()))); continue
        else:
            raise SystemExit(f"unknown tag {tag!r} on block {b} {side}")
        markers.setdefault(name, []).extend(zip(e[:-1], e[1:]))

# every untagged off-axis face must be shared by another block (interface)
for b, side, s in faces_untagged:
    shared = any(s == s2 for b2, sd2, s2 in faces_untagged if (b2, sd2) != (b, side))
    if not shared:
        raise SystemExit(f"block {b} {side}: untagged face is not an interface")

with open(out, "w") as f:
    f.write("NDIME= 2\n")
    f.write(f"NELEM= {len(quads)}\n")
    for k, q in enumerate(quads):
        f.write(f"9 {q[0]} {q[1]} {q[2]} {q[3]} {k}\n")
    f.write(f"NPOIN= {len(nodes)}\n")
    for k, (x, y) in enumerate(nodes):
        f.write(f"{x:.15e} {y:.15e} {k}\n")
    f.write(f"NMARK= {len(markers)}\n")
    for name, segs in markers.items():
        f.write(f"MARKER_TAG= {name}\nMARKER_ELEMS= {len(segs)}\n")
        for a, c in segs:
            f.write(f"3 {a} {c}\n")
np.savez(out.replace(".su2", "") + "_idmap.npz", **idmaps)
print(f"{out}: {len(quads)} quads, {len(nodes)} points, markers "
      + ", ".join(f"{n}={len(s)}" for n, s in markers.items())
      + f", interfaces={len(faces_untagged)//2}")
