#!/usr/bin/env python3
"""Convert an SST restart (k, omega) into a Spalart-Allmaras seed (Nu_Tilde).

SU2 stores one turbulence variable for SA and two for SST, so an SA run cannot
restart from an SST solution directly. The mean flow is carried over unchanged
and the turbulence field is initialized from the equivalent eddy viscosity,
nu_t = k/omega, which for SA equals nu_tilde up to the near-wall damping
function fv1 (fv1 -> 1 away from the wall). Values are floored at the freestream
level SU2 would use, FREESTREAM_NU_FACTOR * mu_inf/rho_inf.

usage: sst_to_sa_seed.py SST_RESTART.csv OUT.csv [NU_FACTOR]
"""
import sys
import numpy as np

src, out = sys.argv[1], sys.argv[2]
NU_FACTOR = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
G, R = 1.4, 296.8
MU_REF, T_REF, S = 1.663e-5, 273.0, 107.0
PA, TA = 101325.0, 300.0

d = np.genfromtxt(src, delimiter=",", names=True)
rho = d["Density"]; u = d["Momentum_x"] / rho; v = d["Momentum_y"] / rho
k = d["Turb_Kin_Energy"]; om = d["Omega"]
nut = k / np.maximum(om, 1e-20)

mu_inf = MU_REF * (TA / T_REF) ** 1.5 * (T_REF + S) / (TA + S)
rho_inf = PA / (R * TA)
nu_floor = NU_FACTOR * mu_inf / rho_inf
nut = np.clip(nut, nu_floor, None)

with open(out, "w") as f:
    f.write('"PointID","x","y","Density","Momentum_x","Momentum_y","Energy","Nu_Tilde"\n')
    for i in range(len(rho)):
        f.write(f"{int(d['PointID'][i])},{d['x'][i]:.15e},{d['y'][i]:.15e},{rho[i]:.15e},"
                f"{d['Momentum_x'][i]:.15e},{d['Momentum_y'][i]:.15e},{d['Energy'][i]:.15e},{nut[i]:.15e}\n")
print(f"{out}: {len(rho)} points, nu_tilde median {np.median(nut):.3e}, max {nut.max():.3e}, "
      f"floor {nu_floor:.3e} applied to {(nut <= nu_floor * 1.0001).sum()} points")
print("NOTE: SST stores total energy including k; SA does not. The carried-over energy "
      "therefore includes the (small) k contribution and relaxes within a few steps.")
