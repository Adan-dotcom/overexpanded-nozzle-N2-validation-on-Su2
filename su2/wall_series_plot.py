#!/usr/bin/env python3
"""Mira la serie temporal de la pared: deriva vs oscilacion, y que se puede decir del espectro.

uso: wall_series_plot.py SERIE.csv SALIDA.png [etiqueta]
"""
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SER, OUT = sys.argv[1], sys.argv[2]
LAB = sys.argv[3] if len(sys.argv) > 3 else ""

d = np.genfromtxt(SER, delimiter=",", names=True)
t = d["t_s"] * 1e3                      # ms
x = d["x_p50_rt"] * 10                  # mm desde la garganta
fs = 1.0 / np.median(np.diff(d["t_s"]))

half = len(t) // 2
print("ventana completa : media %.2f mm  desv %.2f" % (np.nanmean(x), np.nanstd(x)))
print("segunda mitad    : media %.2f mm  desv %.2f" % (np.nanmean(x[half:]), np.nanstd(x[half:])))
print("ultimo cuarto    : media %.2f mm  desv %.2f"
      % (np.nanmean(x[3 * len(t) // 4:]), np.nanstd(x[3 * len(t) // 4:])))

# tendencia lineal en la segunda mitad: si domina, es transitorio, no oscilacion
sl, ic = np.polyfit(t[half:], x[half:], 1)
resid = x[half:] - (sl * t[half:] + ic)
print("segunda mitad: pendiente %.2f mm/ms, dispersion alrededor de la recta %.2f mm"
      % (sl, np.nanstd(resid)))

fig, axs = plt.subplots(1, 2, figsize=(11, 3.9))

ax = axs[0]
ax.plot(t, x, color="#1f6feb", lw=1)
ax.plot(t[half:], sl * t[half:] + ic, "r--", lw=1.5,
        label="tendencia 2a mitad: %.1f mm/ms" % sl)
ax.set_xlabel("tiempo [ms]")
ax.set_ylabel("posicion de la subida de presion [mm]")
ax.set_title("Movimiento del pie del choque  " + LAB, fontsize=10)
ax.legend(fontsize=8)
ax.grid(alpha=.3)

# PSD de la fluctuacion alrededor de la tendencia (quita el transitorio)
ax = axs[1]
seg = x[half:] - (sl * t[half:] + ic)
seg = seg - seg.mean()
n = len(seg)
w = np.hanning(n)
f = np.fft.rfftfreq(n, 1 / fs)
P = np.abs(np.fft.rfft(seg * w)) ** 2 / (fs * (w ** 2).sum())
ax.loglog(f[1:], P[1:], color="#1f6feb", lw=1)
for fr, lab in [(300, "300 Hz"), (800, "800 Hz")]:
    ax.axvline(fr, color="#d62728", ls="--", lw=1)
    ax.text(fr, P[1:].max() * 0.4, lab, color="#d62728", fontsize=8, rotation=90, va="top")
df = fs / n
ax.axvspan(f[1] if len(f) > 1 else 1, df * 2, color="#999", alpha=.25)
ax.text(df * 2.2, P[1:].max() * 0.02,
        "por debajo de ~%.0f Hz el registro\nes demasiado corto: sin informacion" % (df * 2),
        fontsize=7.5, color="#555")
ax.set_xlabel("frecuencia [Hz]")
ax.set_ylabel("densidad espectral de $x_{choque}$")
ax.set_title("Lo que el registro permite decir (df = %.0f Hz)" % df, fontsize=10)
ax.grid(alpha=.3, which="both")

fig.tight_layout()
fig.savefig(OUT, dpi=140)
print("escrito", OUT)
