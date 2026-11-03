# -*- coding: utf-8 -*-
"""Verifica la tabla nueva: el signo de p y la exactitud en el estado AMBIENTE."""
import sys
import numpy as np
import cantera as ct

TAB = sys.argv[1] if len(sys.argv) > 1 else "/mnt/d/eilnerCC/hot/table_rhoe_v2.csv"
d = np.genfromtxt(TAB, delimiter=",", names=True)
rho, e = d["Density"], d["Energy"]
s, dsdrho, dsde = d["s"], d["dsdrho_e"], d["dsde"]
T_tab, p_tab = d["T"], d["p"]

T_rec = 1.0 / dsde
p_rec = -rho ** 2 * T_rec * dsdrho

print("tabla: %s  (%d puntos)" % (TAB.split("/")[-1], len(d)))
print("  rho %.4e a %.4e   |   e %.4e a %.4e"
      % (rho.min(), rho.max(), e.min(), e.max()))
print()
print("SIGNO: p = -rho^2 T (ds/drho)_e  sobre las columnas escritas")
print("  p recuperada negativa en %d de %d puntos" % ((p_rec < 0).sum(), len(d)))
m = np.isfinite(p_rec) & (p_tab > 0)
err_p = np.abs(p_rec[m] - p_tab[m]) / p_tab[m] * 100
err_T = np.abs(T_rec[m] - T_tab[m]) / T_tab[m] * 100
print("  error en p: medio %.3f %%   p95 %.3f %%   max %.3f %%"
      % (err_p.mean(), np.percentile(err_p, 95), err_p.max()))
print("  error en T: medio %.3f %%   p95 %.3f %%   max %.3f %%"
      % (err_T.mean(), np.percentile(err_T, 95), err_T.max()))

# --------------------------------------------- el estado ambiente
g = ct.Solution("h2o2.yaml")
g.TPY = 300.0, 101325.0, "H2:1.0, O2:6.0"
g.equilibrate("TP")
r_a, e_a = g.density, g.int_energy_mass
print()
print("ESTADO AMBIENTE: rho %.4f  e %.4e  (T %.1f K, p %.0f Pa)"
      % (r_a, e_a, g.T, g.P))
dentro = (rho.min() <= r_a <= rho.max()) and (e.min() <= e_a <= e.max())
print("  dentro del dominio de la tabla: %s" % ("SI" if dentro else "NO"))
if dentro:
    i = np.argmin((np.log(rho / r_a)) ** 2 + ((e - e_a) / abs(e_a)) ** 2)
    print("  punto mas cercano: rho %.4f  e %.4e" % (rho[i], e[i]))
    print("  T tabla %.1f  T recuperada %.1f  (dif %.2f %%)"
          % (T_tab[i], T_rec[i], abs(T_rec[i] - T_tab[i]) / T_tab[i] * 100))
    print("  p tabla %.0f  p recuperada %.0f  (dif %.2f %%)"
          % (p_tab[i], p_rec[i], abs(p_rec[i] - p_tab[i]) / p_tab[i] * 100))

# --------------------------------------------- exactitud por zonas de energia
print()
print("EXACTITUD POR ZONA DE ENERGIA (donde esta el ambiente es la zona fria):")
bordes = np.linspace(e.min(), e.max(), 6)
for a, b in zip(bordes[:-1], bordes[1:]):
    z = m & (e[m] >= a) & (e[m] < b) if m.sum() == len(d) else None
    sel = (e >= a) & (e < b) & m
    if sel.sum() == 0:
        continue
    eT = np.abs(T_rec[sel] - T_tab[sel]) / T_tab[sel] * 100
    eP = np.abs(p_rec[sel] - p_tab[sel]) / p_tab[sel] * 100
    marca = "  <<< aqui cae el ambiente" if a <= e_a < b else ""
    print("  e %.3e a %.3e (T %4.0f-%4.0f K): err T %6.3f %%  err p %6.3f %%%s"
          % (a, b, T_tab[sel].min(), T_tab[sel].max(), eT.mean(), eP.mean(), marca))
