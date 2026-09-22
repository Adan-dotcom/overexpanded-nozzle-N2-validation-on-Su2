#!/usr/bin/env python3
"""Initial condition for SU2, identical in intent to the Eilmer Phase 1 case:
converging section (inlet -> throat) filled with reservoir gas at rest,
everything else ambient at rest.  Column layout and energy definition copied
from the previous campaign's generate_seed.py (energy excludes tke).

usage: make_seed.py MESH.su2 OUT.csv P0 T0 P_AMB T_AMB GEOMETRY.lua
"""
import sys, re, math

mesh, out = sys.argv[1], sys.argv[2]
P0, T0, PA, TA = map(float, sys.argv[3:7])
geo = sys.argv[7]
GAMMA, R = 1.4, 296.8                      # N2
MU_REF, T_REF, S = 1.663e-5, 273.0, 107.0  # Sutherland, N2 (same as the .cfg)
pts = [(float(a), float(b)) for a, b in
       re.findall(r"\{\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\}", open(geo).read())]
it = min(range(len(pts)), key=lambda k: pts[k][1])
x_t = pts[it][0]


def r_wall(x):
    for (xa, ra), (xb, rb) in zip(pts[:-1], pts[1:]):
        if xa <= x <= xb:
            return ra + (rb - ra) * (x - xa) / (xb - xa)
    return pts[-1][1]


def mu(T):
    return MU_REF * (T / T_REF) ** 1.5 * (T_REF + S) / (T + S)


def state(p, T, k, mut_ratio):
    rho = p / (R * T)
    om = rho * k / (mut_ratio * mu(T))
    return rho, p / (GAMMA - 1.0), k, om


# same turbulence levels as the Eilmer case: inlet Tu=5% of u_in (M=0.147),
# mu_t/mu=10; ambient k=0.01, mu_t/mu=1
a0 = math.sqrt(GAMMA * R * T0)
k_in = 1.5 * (0.05 * 0.147 * a0) ** 2
res = state(P0, T0, k_in, 10.0)
amb = state(PA, TA, 1.0e-2, 1.0)

lines = open(mesh).read().split("\n")
i0 = next(i for i, l in enumerate(lines) if l.startswith("NPOIN="))
n = int(lines[i0].split("=")[1].split()[0])
nres = 0
with open(out, "w") as f:
    f.write('"PointID","x","y","Density","Momentum_x","Momentum_y","Energy","Turb_Kin_Energy","Omega"\n')
    for k in range(n):
        x, y = map(float, lines[i0 + 1 + k].split()[:2])
        in_conv = x <= x_t + 1e-12 and y <= r_wall(x) + 1e-9
        rho, E, tke, om = res if in_conv else amb
        nres += in_conv
        f.write(f"{k},{x:.15e},{y:.15e},{rho:.15e},0.0,0.0,{E:.15e},{tke:.15e},{om:.15e}\n")
print(f"{out}: {n} points, {nres} reservoir (x <= {x_t*1e3:.3f} mm), k_in={k_in:.3g} om_in={res[3]:.3g}")
