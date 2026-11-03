# -*- coding: utf-8 -*-
"""Comprueba que el caso caliente se quedo DENTRO del dominio de la tabla.

Los limites se leen de la tabla, no se escriben a mano: la version anterior los traia
codificados (0.01-8.0 y -1.325e7) y no correspondian a la tabla real.
"""
import glob
import os
import re
import sys

import numpy as np

W = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/su2-work/hot_smoke")
TAB = "/mnt/d/eilnerCC/hot/table_rhoe_raw.csv"
RT, XT = 0.010, 0.02268

t = np.genfromtxt(TAB, delimiter=",", names=True)
R_LO, R_HI = t["Density"].min(), t["Density"].max()
E_LO, E_HI = t["Energy"].min(), t["Energy"].max()
print("dominio REAL de la tabla: rho %.4e a %.4e | e %.4e a %.4e"
      % (R_LO, R_HI, E_LO, E_HI))

fs = sorted(glob.glob(os.path.join(W, "wall_*.csv")),
            key=lambda p: int(re.findall(r"wall_(\d+)\.csv", p)[0]))
if not fs:
    sys.exit("NO HAY archivos wall_*.csv en %s: el caso no escribio nada." % W)
f = fs[-1]
d = np.genfromtxt(f, delimiter=",", names=True)
o = np.argsort(d["x"])
x = (d["x"][o] - XT) / RT
rho = d["Density"][o]
E = d["Energy"][o]
k = d["Turb_Kin_Energy"][o] if "Turb_Kin_Energy" in d.dtype.names else 0.0
u = d["Momentum_x"][o] / rho
v = d["Momentum_y"][o] / rho
e = E / rho - 0.5 * (u * u + v * v) - k

print("archivo: %s (%d de %d escritos) | puntos de pared: %d"
      % (os.path.basename(f), len(fs), len(fs), len(x)))
print("rho en la pared: %.4f a %.4f kg/m3" % (rho.min(), rho.max()))
print("e   en la pared: %.4e a %.4e J/kg" % (e.min(), e.max()))
fuera = ((rho < R_LO) | (rho > R_HI) | (e < E_LO) | (e > E_HI))
print("puntos FUERA del dominio de la tabla: %d de %d" % (fuera.sum(), len(x)))
if fuera.sum():
    print("  primeros x/r_t fuera:", np.round(x[fuera][:8], 2))
print("velocidad maxima en la pared: %.0f m/s" % np.hypot(u, v).max())
print("NaN en la solucion: %d" % (~np.isfinite(rho)).sum())

# senal POSITIVA de exito, no ausencia de error
ok = (fuera.sum() == 0) and np.isfinite(rho).all() and len(fs) >= 2
print()
print("VEREDICTO:", "PASA" if ok else "NO PASA")
sys.exit(0 if ok else 1)
