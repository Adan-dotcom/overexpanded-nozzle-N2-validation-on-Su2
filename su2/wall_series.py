#!/usr/bin/env python3
"""Serie temporal de la pared a partir de los archivos wall_*.csv que SU2 escribe cada 50 pasos.

Los restarts (cada 2500 pasos) son una muestra cada 250 us: demasiado pocas para ver
nada temporal. Los wall_*.csv son una muestra cada 50 pasos y pesan poco, asi que dan
dos ordenes de magnitud mas de resolucion temporal por el mismo costo de computo.

Produce un CSV compacto con, por instante:
  t, x_shock (posicion del pie del choque, maximo de dp/dx), p_w en estaciones fijas.

uso: wall_series.py RUN_DIR DT SALIDA.csv
"""
import glob
import os
import re
import sys

import numpy as np

RUN, DT, OUT = sys.argv[1], float(sys.argv[2]), sys.argv[3]
G, R, PA, RT, XT = 1.4, 296.8, 101325.0, 0.010, 0.02268
STATIONS = [2.56, 3.36, 4.16, 4.95, 5.75, 6.55, 7.35, 8.14, 8.94, 9.73, 10.53, 11.33, 12.12]

files = sorted(glob.glob(os.path.join(RUN, "wall_*.csv")),
               key=lambda f: int(re.findall(r"wall_(\d+)\.csv", f)[0]))
if not files:
    sys.exit("no hay archivos wall_*.csv en " + RUN)

rows = []
for f in files:
    step = int(re.findall(r"wall_(\d+)\.csv", f)[0])
    d = np.genfromtxt(f, delimiter=",", names=True)
    x = d["x"]
    o = np.argsort(x)
    x = x[o]
    rho = d["Density"][o]
    k = d["Turb_Kin_Energy"][o] if "Turb_Kin_Energy" in d.dtype.names else 0.0
    u = d["Momentum_x"][o] / rho
    v = d["Momentum_y"][o] / rho
    T = (G - 1) / R * (d["Energy"][o] / rho - 0.5 * (u * u + v * v) - k)
    p = rho * R * T / PA                      # p_w/p_a
    xr = (x - XT) / RT                        # x/r_t desde la garganta

    # solo la divergente, y sin el labio de salida (ahi el gradiente tambien es enorme)
    m = (xr > 1.0) & (xr < 11.5)
    xr_d, p_d = xr[m], p[m]

    # posicion de la subida de presion: primer cruce de p_w/p_a = 0.5, interpolado.
    # Es monotono y robusto, a diferencia del maximo de dp/dx.
    x50 = np.nan
    c = np.where((p_d[:-1] < 0.5) & (p_d[1:] >= 0.5))[0]
    if len(c):
        j = c[0]
        x50 = xr_d[j] + (0.5 - p_d[j]) * (xr_d[j + 1] - xr_d[j]) / (p_d[j + 1] - p_d[j])

    # pie del choque: maximo del gradiente de presion, con parabola para sub-celda
    dp = np.gradient(p_d, xr_d)
    i = int(np.argmax(dp))
    if 0 < i < len(dp) - 1:
        y0, y1, y2 = dp[i - 1], dp[i], dp[i + 1]
        den = y0 - 2 * y1 + y2
        off = 0.5 * (y0 - y2) / den if den != 0 else 0.0
        xsh = xr_d[i] + off * (xr_d[i + 1] - xr_d[i - 1]) / 2
    else:
        xsh = xr_d[i]

    rows.append([step * DT, x50, xsh, float(dp[i])] + [float(np.interp(s, xr, p)) for s in STATIONS])

rows = np.array(rows)
hdr = "t_s,x_p50_rt,x_shock_rt,dpdx_max," + ",".join("p_%0.2f" % s for s in STATIONS)
np.savetxt(OUT, rows, delimiter=",", header=hdr, comments="", fmt="%.6e")

t = rows[:, 0]
xs = rows[:, 1]
xsh_c = rows[:, 2]
fs = 1.0 / (t[1] - t[0])
print("%d instantes | registro %.3f ms | fs = %.0f kHz | Nyquist = %.0f kHz"
      % (len(t), (t[-1] - t[0]) * 1e3, fs / 1e3, fs / 2e3))
print("resolucion espectral del registro completo: df = %.0f Hz" % (1.0 / (t[-1] - t[0])))
print("x_dpdx : media %.3f  desv %.3f  rango %.3f (x/r_t)" % (np.nanmean(xsh_c), np.nanstd(xsh_c), np.nanmax(xsh_c)-np.nanmin(xsh_c)))
print("x(p=0.5): media %.3f  desv %.3f  min %.3f  max %.3f  (x/r_t)"
      % (np.nanmean(xs), np.nanstd(xs), np.nanmin(xs), np.nanmax(xs)))
print("         en mm desde la garganta: media %.2f  desv %.2f  rango %.2f"
      % (np.nanmean(xs) * 10, np.nanstd(xs) * 10, (np.nanmax(xs) - np.nanmin(xs)) * 10))
print("escrito", OUT)
