#!/usr/bin/env python3
"""Where is an equation misbehaving?  Compares two CONSECUTIVE restarts (steps N-1 and N, the pair
SU2 writes for BDF2) and prints the points where a field changes most in one physical step.

Why this and not the residual field: SU2 does not put residuals in restart_*.csv (only the
solution variables), and on L3 at NPR 33 rms[w] jumped from ~10^0.4 to ~10^3.7 at step ~189 800
while rms[Rho] stayed healthy, i.e. something local. A cell whose omega does not converge within
the step also jumps from one step to the next, so the one-step change points at it.

usage: where_residual.py RESTART_N-1.csv RESTART_N.csv [FIELD] [N]
       FIELD default Omega; for Omega and Turb_Kin_Energy the change is |log10(q_N / q_N-1)|,
       for other fields |dq| / max|q|.
"""
import sys

import numpy as np

fa, fb = sys.argv[1], sys.argv[2]
field = sys.argv[3] if len(sys.argv) > 3 else "Omega"
n = int(sys.argv[4]) if len(sys.argv) > 4 else 15


def rd(f):
    d = np.genfromtxt(f, delimiter=",", names=True)
    return d[np.argsort(d["PointID"].astype(int))]


a, b = rd(fa), rd(fb)
if field not in a.dtype.names:
    sys.exit("no column %s; columns: %s" % (field, a.dtype.names))
x, y = b["x"] * 1e3, b["y"] * 1e3
qa, qb = a[field], b[field]
if field in ("Omega", "Turb_Kin_Energy"):
    tiny = 1e-30
    ch = np.abs(np.log10(np.maximum(np.abs(qb), tiny) / np.maximum(np.abs(qa), tiny)))
    unit = "|log10 ratio|"
else:
    ch = np.abs(qb - qa) / np.abs(qa).max()
    unit = "|dq|/max|q|"
o = np.argsort(ch)[::-1]
print("%s -> %s  field %s  change %s: rms %.3e  max %.3e  (%d points)"
      % (fa, fb, field, unit, np.sqrt((ch ** 2).mean()), ch.max(), len(ch)))
print("top %d points (mm; throat at x = 22.68 mm, nozzle exit near x = 147.7 mm):" % n)
for i in o[:n]:
    print("  x %8.2f  y %8.2f  change %.3e   %s %.4e -> %.4e" % (x[i], y[i], ch[i], field, qa[i], qb[i]))
s = ch ** 2
s = s / s.sum() if s.sum() > 0 else s
regions = {
    "inside nozzle (x < 148 mm)": x < 148,
    "lip and near plume (148-250 mm)": (x >= 148) & (x < 250),
    "far field (x >= 250 mm)": x >= 250,
}
print("share of sum of squares: " + "; ".join("%s %.0f%%" % (k, 100 * s[m].sum()) for k, m in regions.items()))
