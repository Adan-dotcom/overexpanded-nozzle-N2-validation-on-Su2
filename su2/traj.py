#!/usr/bin/env python3
"""Trayectoria y deriva del pie del choque a partir de un serie_*.csv de wall_series.py.

uso: traj_l1.py SERIE.csv [CADA]
Imprime la trayectoria en mm desde la garganta y la deriva de la segunda mitad,
que es el criterio de asentamiento de la campana (< 0.5 mm/ms).
"""
import csv
import sys

path = sys.argv[1]
every = int(sys.argv[2]) if len(sys.argv) > 2 else 8

rows = list(csv.DictReader(open(path)))
if not rows:
    sys.exit("serie vacia: " + path)

cols = list(rows[0].keys())
tcol = "t" if "t" in cols else cols[0]
# x_p50_rt (cruce de p_w/p_a = 0.5) antes que x_shock_rt: wall_series.py lo elige
# por monotono y robusto frente al maximo de dp/dx. dpdx_max NO es una posicion,
# es la magnitud del gradiente -- tomarla por posicion da numeros sin sentido.
for pref in ("x_p50_rt", "x_shock_rt"):
    if pref in cols:
        xcol = pref
        break
else:
    sys.exit("no hay columna de posicion reconocible en " + path)
print("columna de posicion:", xcol, "| columna de tiempo:", tcol)

def t_ms(r):
    return float(r[tcol]) * 1e3

def x_mm(r):
    return float(r[xcol]) * 10.0      # x/r_t -> mm desde la garganta (r_t = 10 mm)

print("\ntrayectoria:")
for i in range(0, len(rows), every):
    r = rows[i]
    print("  t=%7.3f ms   x=%7.2f mm" % (t_ms(r), x_mm(r)))
r = rows[-1]
print("  t=%7.3f ms   x=%7.2f mm   <- ultimo" % (t_ms(r), x_mm(r)))

half = rows[len(rows) // 2:]
dt = t_ms(half[-1]) - t_ms(half[0])
dx = x_mm(half[-1]) - x_mm(half[0])
xs = [x_mm(r) for r in half]
mean = sum(xs) / len(xs)
var = sum((v - mean) ** 2 for v in xs) / len(xs)
print("\nsegunda mitad del registro (%.3f a %.3f ms):" % (t_ms(half[0]), t_ms(half[-1])))
print("  media       %7.2f mm   desv %.2f mm" % (mean, var ** 0.5))
if dt > 0:
    d = dx / dt
    print("  deriva      %+7.2f mm/ms  -> %s el criterio de 0.5 mm/ms"
          % (d, "CUMPLE" if abs(d) < 0.5 else "NO CUMPLE"))
print("  recorrido total del registro: %.2f mm" % (max(x_mm(r) for r in rows)
                                                  - min(x_mm(r) for r in rows)))
