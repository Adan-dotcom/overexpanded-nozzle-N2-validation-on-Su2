#!/usr/bin/env python3
"""Espectro de la presion de pared a partir de una serie densa, con el metodo de Welch.

Se analiza la presion en estaciones fijas (no x_sep): x_sep esta cuantizado al tamano de
celda de la pared y por debajo de ~1 mm su espectro es ruido de discretizacion.

uso: spectra.py SERIE.csv SALIDA.png [t_inicio_ms]
"""
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SER, OUT = sys.argv[1], sys.argv[2]
T0 = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0     # ms a descartar (transitorio)

d = np.genfromtxt(SER, delimiter=",", names=True)
t = d["t_s"]
fs = 1.0 / np.median(np.diff(t))
m = t * 1e3 >= T0
t = t[m]
T = t[-1] - t[0]
print("registro util: %.2f ms  fs = %.0f kHz  muestras = %d" % (T * 1e3, fs / 1e3, m.sum()))


def welch(x, nseg):
    """PSD unilateral promediando nseg segmentos con 50% de solape y ventana de Hann."""
    x = x - x.mean()
    n = len(x)
    L = n // ((nseg + 1) // 2) if nseg > 1 else n
    L = min(L, n)
    step = L // 2 if nseg > 1 else L
    w = np.hanning(L)
    U = (w ** 2).sum()
    segs = [x[i:i + L] for i in range(0, n - L + 1, step)]
    P = np.zeros(L // 2 + 1)
    for s in segs:
        P += np.abs(np.fft.rfft(s * w)) ** 2
    P = P / (len(segs) * fs * U)
    P[1:-1] *= 2
    return np.fft.rfftfreq(L, 1 / fs), P, len(segs), fs / L


fig, ax = plt.subplots(figsize=(7.6, 4.6))
COLS = [("p_735", "x/r_t = 7.35 (zona de interaccion)", "#d62728"),
        ("p_814", "x/r_t = 8.14 (aguas abajo de la separacion)", "#1f6feb"),
        ("p_456", "x/r_t = 4.95 (flujo adherido)", "#2ca02c")]
for col, lab, c in COLS:
    key = col if col in d.dtype.names else None
    if key is None:
        cands = [n for n in d.dtype.names if n.startswith("p_")]
        idx = {"p_735": 6, "p_814": 7, "p_456": 3}[col]
        key = cands[idx]
    x = d[key][m]
    f, P, ns, df = welch(x, 4)
    rms = np.sqrt(np.trapz(P[1:], f[1:]))
    ax.loglog(f[1:], P[1:], color=c, lw=1.1, label="%s  (rms %.2e $p_a$)" % (lab, rms))
    print("%-46s media %.4f p_a   rms de fluctuacion %.3e p_a" % (lab, x.mean(), rms))

for fr in (300, 800):
    ax.axvline(fr, color="#888", ls="--", lw=1)
    ax.text(fr, ax.get_ylim()[1] * 0.3, " %d Hz medidos" % fr, fontsize=8, color="#555",
            rotation=90, va="top")
ax.axvspan(f[1] * 0.5, 2 * df, color="#bbb", alpha=.35)
ax.text(2 * df * 1.1, ax.get_ylim()[0] * 30,
        "por debajo de ~%.0f Hz\nel registro no resuelve" % (2 * df), fontsize=7.5, color="#555")
ax.set_xlabel("frecuencia [Hz]")
ax.set_ylabel("PSD de $p_w/p_a$  [1/Hz]")
ax.set_title("Espectro de la presion de pared, registro de %.0f ms\n"
             "Welch, %d segmentos, df = %.0f Hz" % (T * 1e3, ns, df), fontsize=10)
ax.legend(fontsize=7.5, loc="lower left")
ax.grid(alpha=.3, which="both")
fig.tight_layout()
fig.savefig(OUT, dpi=140)
print("escrito", OUT)
