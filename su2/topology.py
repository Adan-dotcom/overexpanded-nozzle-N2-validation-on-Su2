#!/usr/bin/env python3
"""Auditoria de topologia: signo del esfuerzo cortante en la pared de la tobera.

tau_w = mu_w * u_t / d_1, con u_t la velocidad TANGENCIAL CON SIGNO del primer punto
interior (positiva hacia la salida). Donde tau_w cambia de signo hay separacion (+ a -)
o readherencia (- a +). FSS: una separacion y flujo inverso hasta la salida.
RSS: separacion y readherencia dentro de la tobera.

uso: topology.py RUN_DIR [RESTART.csv] [SALIDA.csv]
     (sin RESTART toma el restart_*.csv mas reciente por fecha)
"""
import glob
import os
import sys

import numpy as np

RUN = sys.argv[1]
G, R = 1.4, 296.8
MU_REF, T_REF, S = 1.663e-5, 273.0, 107.0
RT, XT = 0.010, 0.02268

idm = np.load(glob.glob(os.path.join(RUN, "*_idmap.npz"))[0])
if len(sys.argv) > 2 and sys.argv[2].endswith(".csv") and os.path.exists(sys.argv[2]):
    f = sys.argv[2]
else:
    f = max(glob.glob(os.path.join(RUN, "restart_*.csv")), key=os.path.getmtime)
OUT = sys.argv[3] if len(sys.argv) > 3 else None
d = np.genfromtxt(f, delimiter=",", names=True)
d = d[np.argsort(d["PointID"].astype(int))]

X, TAU = [], []
for b in ("b0", "b1", "b2", "b3"):            # solo bloques de la tobera
    if b not in idm.files:
        continue
    ids = idm[b]
    w, i1 = ids[-1], ids[-2]
    xw, yw = d["x"][w], d["y"][w]
    tx, ty = np.gradient(xw), np.gradient(yw)  # tangente de la pared, hacia la salida
    n = np.hypot(tx, ty); tx, ty = tx / n, ty / n
    d1 = np.hypot(d["x"][i1] - xw, d["y"][i1] - yw)
    rho = d["Density"][w]
    k = d["Turb_Kin_Energy"][w] if "Turb_Kin_Energy" in d.dtype.names else 0.0
    Tw = (G - 1) / R * (d["Energy"][w] / rho)   # en la pared u = 0
    Tw = Tw - (G - 1) / R * k / rho if np.ndim(k) else Tw
    mu = MU_REF * (Tw / T_REF) ** 1.5 * (T_REF + S) / (Tw + S)
    r1 = d["Density"][i1]
    ut = (d["Momentum_x"][i1] * tx + d["Momentum_y"][i1] * ty) / r1
    X += list((xw - XT) * 1e3)                  # mm desde la garganta
    TAU += list(mu * ut / np.maximum(d1, 1e-12))
X, TAU = np.array(X), np.array(TAU)
X, iu = np.unique(X, return_index=True); TAU = TAU[iu]
m = X > 1.0                                     # divergente
X, TAU = X[m], TAU[m]

print("instantanea: %s   puntos de pared en la divergente: %d   salida en x = %.2f mm"
      % (os.path.basename(f), len(X), X[-1]))
print("tau_w adherido tipico (mediana, x < 40 mm): %.1f Pa" % np.median(TAU[X < 40]))
sgn = np.sign(TAU)
cross = np.where(sgn[1:] * sgn[:-1] < 0)[0]
ev = []
for i in cross:
    x0 = X[i] - TAU[i] * (X[i + 1] - X[i]) / (TAU[i + 1] - TAU[i])
    ev.append((x0, "SEPARACION" if TAU[i] > 0 else "READHERENCIA"))
for x0, kind in ev:
    print("  x = %7.2f mm   %s" % (x0, kind))
# tramos de flujo inverso y su tamano
rev = TAU < 0
if rev.any():
    edges = np.flatnonzero(np.diff(np.concatenate([[0], rev.astype(int), [0]])))
    for a, b in zip(edges[::2], edges[1::2]):
        print("  flujo inverso de %.2f a %.2f mm (%.2f mm, %d puntos, tau min %.1f Pa)%s"
              % (X[a], X[b - 1], X[b - 1] - X[a], b - a, TAU[a:b].min(),
                 "  <- llega a la salida" if b == len(X) else ""))
    main = max(zip(edges[::2], edges[1::2]), key=lambda ab: ab[1] - ab[0])
    if main[1] == len(X):
        verdict = "FSS: el flujo inverso principal llega hasta la salida, sin readherencia"
    else:
        verdict = ("RSS: readherencia en x = %.2f mm, dentro de la tobera (burbuja de %.2f mm)"
                   % (X[main[1] - 1], X[main[1] - 1] - X[main[0]]))
else:
    verdict = "ADHERIDO: no hay flujo inverso en la pared"
print("VEREDICTO:", verdict)
if OUT:
    np.savetxt(OUT, np.column_stack([X, TAU]), delimiter=",", header="x_mm,tau_w_Pa", comments="")
    print("escrito", OUT)
