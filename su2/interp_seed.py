#!/usr/bin/env python3
"""Interpolate an SU2 restart CSV (conservative variables) from one mesh onto
another mesh's points and write it as a seed_00000.csv.  Linear (Delaunay)
interpolation; points outside the source hull take the nearest value.
omega is interpolated in log space.  Wall-marker nodes get zero momentum.

usage: interp_seed.py SRC_RESTART.csv DST_MESH.su2 OUT.csv
"""
import sys
import numpy as np
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

src, mesh, out = sys.argv[1:4]
d = np.genfromtxt(src, delimiter=",", names=True)
cols = ["Density", "Momentum_x", "Momentum_y", "Energy", "Turb_Kin_Energy", "Omega"]
XY = np.column_stack([d["x"], d["y"]])
V = np.column_stack([d[c] for c in cols]); V[:, 5] = np.log(V[:, 5])

lines = open(mesh).read().split("\n")
i0 = next(i for i, l in enumerate(lines) if l.startswith("NPOIN="))
n = int(lines[i0].split("=")[1].split()[0])
P = np.array([[float(v) for v in lines[i0 + 1 + k].split()[:2]] for k in range(n)])
wall = set()
for i, l in enumerate(lines):
    if l.startswith("MARKER_TAG=") and l.split("=")[1].strip() == "WALL":
        m = int(lines[i + 1].split("=")[1])
        for s in lines[i + 2:i + 2 + m]:
            wall.update(int(t) for t in s.split()[1:])

W = LinearNDInterpolator(XY, V)(P)
bad = np.isnan(W).any(axis=1)
W[bad] = NearestNDInterpolator(XY, V)(P[bad])
W[:, 5] = np.exp(W[:, 5])
wl = np.array(sorted(wall)); W[wl, 1] = 0.0; W[wl, 2] = 0.0

# Rescale omega near the wall to the target mesh.  SST's wall treatment gives
# omega ~ 6*nu/(beta1*d^2) in the viscous sublayer, so a seed interpolated from a
# coarser mesh (larger first cell) carries an omega that is orders of magnitude
# too small there -> mu_t far too large -> the boundary layer restructures
# violently.  Raising omega to the sublayer value is the standard initialization.
GAMMA, R, BETA1 = 1.4, 296.8, 0.075
MU_REF, T_REF, S = 1.663e-5, 273.0, 107.0
rho = W[:, 0]
T = (GAMMA - 1) / R * (W[:, 3] / rho - 0.5 * (W[:, 1] ** 2 + W[:, 2] ** 2) / rho ** 2 - W[:, 4])
nu = MU_REF * (T / T_REF) ** 1.5 * (T_REF + S) / (T + S) / rho
if len(wl):
    from scipy.spatial import cKDTree
    d = cKDTree(P[wl]).query(P)[0]                      # distance to the nearest wall node
    d = np.maximum(d, 1e-9)
    om_sub = np.minimum(6.0 * nu / (BETA1 * d ** 2), 1.0e10)   # clip: no unphysical spikes
    on_wall = np.zeros(len(P), bool); on_wall[wl] = True        # SU2 imposes omega there itself
    raised = (d < 1e-3) & (om_sub > W[:, 5]) & ~on_wall
    factor = np.max(om_sub[raised] / W[raised, 5]) if raised.any() else 1.0
    W[raised, 5] = om_sub[raised]
    print(f"  omega raised to the sublayer value at {raised.sum()} near-wall points "
          f"(max factor {factor:.3g}, new max {W[:, 5].max():.3g})")
with open(out, "w") as f:
    f.write('"PointID","x","y",' + ",".join(f'"{c}"' for c in cols) + "\n")
    for k in range(n):
        f.write(f"{k},{P[k,0]:.15e},{P[k,1]:.15e}," + ",".join(f"{v:.15e}" for v in W[k]) + "\n")
print(f"{out}: {n} points, {bad.sum()} by nearest, {len(wl)} wall nodes zeroed")
