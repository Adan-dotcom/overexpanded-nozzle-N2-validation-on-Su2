#!/usr/bin/env python3
"""Mide y+ sobre una solucion convergida (no lo estima a partir de la especificacion de malla).

y+ se calcula con el esfuerzo cortante de la propia solucion:
    tau_w = mu_w * u_1 / d_1        (u_1 = velocidad tangencial del primer punto interior)
    u_tau = sqrt(tau_w / rho_w)
    y+    = rho_w * u_tau * d_1 / mu_w
Reporta la distribucion completa a lo largo de la pared, no un solo numero.

uso: yplus.py RUN_DIR [SALIDA.png]
"""
import glob
import os
import re
import sys

import numpy as np

RUN = sys.argv[1]
PNG = sys.argv[2] if len(sys.argv) > 2 else None
G, R = 1.4, 296.8
MU_REF, T_REF, S = 1.663e-5, 273.0, 107.0
RT, XT = 0.010, 0.02268

idm = np.load(glob.glob(os.path.join(RUN, "*_idmap.npz"))[0])
f = sorted(glob.glob(os.path.join(RUN, "restart_*.csv")),
           key=lambda p: int(re.findall(r"(\d+)\.csv", p)[0]))[-1]
d = np.genfromtxt(f, delimiter=",", names=True)
o = np.argsort(d["PointID"].astype(int))
d = d[o]

X, Y, YP = [], [], []
for b in idm.files:
    ids = idm[b]
    if ids.ndim != 2 or ids.shape[0] < 2:
        continue
    w, i1 = ids[-1], ids[-2]              # fila de pared y primera fila interior
    xw, yw = d["x"][w], d["y"][w]
    x1, y1 = d["x"][i1], d["y"][i1]
    d1 = np.hypot(x1 - xw, y1 - yw)       # distancia normal al primer centro de celda

    rho = d["Density"][w]
    k = d["Turb_Kin_Energy"][w] if "Turb_Kin_Energy" in d.dtype.names else 0.0
    uw, vw = d["Momentum_x"][w] / rho, d["Momentum_y"][w] / rho
    Tw = (G - 1) / R * (d["Energy"][w] / rho - 0.5 * (uw ** 2 + vw ** 2) - k)
    mu = MU_REF * (Tw / T_REF) ** 1.5 * (T_REF + S) / (Tw + S)

    r1 = d["Density"][i1]
    u1 = np.hypot(d["Momentum_x"][i1] / r1, d["Momentum_y"][i1] / r1)

    tau = mu * u1 / np.maximum(d1, 1e-12)
    utau = np.sqrt(tau / rho)
    X += list((xw - XT) / RT)
    Y += list(d1 * 1e6)                   # micras
    YP += list(rho * utau * d1 / mu)

X, Y, YP = np.array(X), np.array(Y), np.array(YP)
o = np.argsort(X)
X, Y, YP = X[o], Y[o], YP[o]
div = X > 0                               # divergente, que es lo que importa

print("instantanea: %s   puntos de pared: %d" % (os.path.basename(f), len(X)))
print("primera celda: %.1f um (mediana en la divergente)" % np.median(Y[div]))
for lab, m in [("toda la pared", np.ones_like(X, bool)), ("solo la divergente", div)]:
    v = YP[m]
    print("y+ %-20s mediana %6.2f   media %6.2f   p95 %6.2f   max %6.2f"
          % (lab, np.median(v), v.mean(), np.percentile(v, 95), v.max()))

if PNG:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.2, 4))
    ax.semilogy(X, YP, ".", ms=3, color="#1f6feb")
    ax.axhline(1, color="#2ca02c", lw=1.2)
    ax.axhspan(5, 30, color="#d62728", alpha=.10)
    ax.text(X.max(), 1.15, "y+ = 1", color="#2ca02c", fontsize=8, ha="right")
    ax.set_xlabel("$x/r_t$ desde la garganta")
    ax.set_ylabel("$y^+$ de la primera celda")
    ax.set_title("$y^+$ medido sobre la solucion  (%s)" % os.path.basename(RUN.rstrip("/")),
                 fontsize=10)
    ax.grid(alpha=.3, which="both")
    fig.tight_layout()
    fig.savefig(PNG, dpi=140)
    print("escrito", PNG)
