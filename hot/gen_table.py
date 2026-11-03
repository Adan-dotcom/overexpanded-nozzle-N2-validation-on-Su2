#!/usr/bin/env python3
"""Genera los datos crudos de la tabla (rho, e) que pide DATADRIVEN_FLUID de SU2.

SU2 recupera TODA la termodinamica de la entropia y sus derivadas:
    s(rho,e), ds/drho|e, ds/de|rho, d2s/drho2, d2s/dedrho, d2s/de2
(ver SU2_CFD/src/fluid/CDataDrivenFluid.cpp). Aqui se calculan con Cantera en
EQUILIBRIO quimico, porque el paso 1 mostro que congelar la composicion cambia la
temperatura de salida hasta un 22%.

Salida: CSV con las 8 columnas. La conversion al formato .drg que lee SU2 se hace
despues con SU2_DataMiner; este paso se verifica solo, por round-trip.
"""
import os
import sys

import numpy as np
import cantera as ct

MECH = "h2o2.yaml"
OF = 6.0
P0, T0 = 100e5, 3528.5   # T de llama calculada (auditoria 2026-11-03)
NR, NE = int(sys.argv[1]) if len(sys.argv) > 1 else 60, int(sys.argv[2]) if len(sys.argv) > 2 else 60
OUT = os.environ.get("OUT", "/mnt/d/eilnerCC/hot/table_rhoe_raw.csv")

g = ct.Solution(MECH)
mH2, mO2 = 1.0, OF
g.TPY = 300.0, P0, "H2:%f, O2:%f" % (mH2, mO2)
Yelem = g.Y.copy()


def u_at(T, rho):
    """Energia interna del equilibrio a (T, rho). equilibrate(TV) es mucho mas robusto
    que fijar UV directamente, que no converge si el punto de partida esta lejos."""
    g.TD = T, rho
    g.equilibrate("TV")
    return g.int_energy_mass


def eq_state(rho, e, lo=200.0, hi=6000.0):
    """Resuelve T tal que u_eq(T,rho) = e por biseccion. Devuelve T, p, s."""
    ulo, uhi = u_at(lo, rho), u_at(hi, rho)
    if not (ulo <= e <= uhi):
        raise ValueError("e fuera del rango alcanzable a esta densidad")
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if u_at(mid, rho) < e:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-3:
            break
    g.TD = 0.5 * (lo + hi), rho
    g.equilibrate("TV")
    return g.T, g.P, g.entropy_mass


# --- recorrido de la isentropa para acotar el dominio de la tabla
g.TPY = T0, P0, Yelem
g.equilibrate("TP")
s0 = g.entropy_mass
rhos, es = [], []
for p in np.logspace(np.log10(P0), np.log10(0.2e5), 40):
    g.SP = s0, p
    g.equilibrate("SP")
    rhos.append(g.density)
    es.append(g.int_energy_mass)
rhos, es = np.array(rhos), np.array(es)
print("isentropa de referencia: rho de %.4f a %.4f kg/m3,  e de %.3e a %.3e J/kg"
      % (rhos.min(), rhos.max(), es.min(), es.max()))

# margen del 40% alrededor de la isentropa (el choque y la recirculacion salen de ella)
span = es.max() - es.min()
# El dominio se puede forzar por variables de entorno: la malla del CFD incluye el
# ambiente frio, que queda MUY fuera del rango de la isentropa de la tobera.
rlo = float(os.environ.get("RHO_LO", rhos.min() * 0.7))
rhi = float(os.environ.get("RHO_HI", rhos.max() * 1.5))
elo = float(os.environ.get("E_LO", es.min() - 0.15 * span))
ehi = float(os.environ.get("E_HI", es.max() + 0.15 * span))
rho_grid = np.logspace(np.log10(rlo), np.log10(rhi), NR)
# Malla GRADUADA en energia: la zona fria (donde cae el ambiente) necesita mucha mas
# resolucion porque ahi la recombinacion curva fuerte la superficie s(rho,e). Con malla
# uniforme el error en T y p llega a 2.6 % ahi, contra 0.01 % en la zona caliente.
# El formato .drg es un mapa trapezoidal, no exige malla uniforme.
GRADE = float(os.environ.get("E_GRADE", "1.0"))
tt = np.linspace(0.0, 1.0, NE) ** GRADE
e_grid = elo + (ehi - elo) * tt
print("malla de la tabla: %d x %d = %d estados de equilibrio" % (NR, NE, NR * NE))

S = np.zeros((NR, NE)); T = np.zeros_like(S); Pm = np.zeros_like(S)
bad = 0
for i, rho in enumerate(rho_grid):
    for j, e in enumerate(e_grid):
        try:
            T[i, j], Pm[i, j], S[i, j] = eq_state(rho, e)
        except Exception:
            T[i, j] = Pm[i, j] = S[i, j] = np.nan
            bad += 1
    if i % 10 == 0:
        print("  fila %d/%d" % (i, NR), flush=True)
print("estados que no convergieron: %d de %d" % (bad, NR * NE))

# --- derivadas de s por diferencias finitas sobre la malla (log-rho uniforme)
lr = np.log(rho_grid)
dsdlr = np.gradient(S, lr, axis=0)
dsde = np.gradient(S, e_grid, axis=1)
dsdrho = dsdlr / rho_grid[:, None]
d2sdrho2 = np.gradient(dsdrho, rho_grid, axis=0)
d2sde2 = np.gradient(dsde, e_grid, axis=1)
d2sdedrho = np.gradient(dsdrho, e_grid, axis=1)

rows = []
for i in range(NR):
    for j in range(NE):
        if np.isnan(S[i, j]):
            continue
        rows.append([rho_grid[i], e_grid[j], S[i, j], dsdrho[i, j], dsde[i, j],
                     d2sdrho2[i, j], d2sdedrho[i, j], d2sde2[i, j], T[i, j], Pm[i, j]])
rows = np.array(rows)
hdr = "Density,Energy,s,dsdrho_e,dsde,d2sdrho2,d2sdedrho,d2sde2,T,p"
np.savetxt(OUT, rows, delimiter=",", header=hdr, comments="", fmt="%.10e")
print("escrito %s  (%d puntos)" % (OUT, len(rows)))

# --- VERIFICACION por round-trip: recuperar p, T y a de las derivadas de s
# Relaciones termodinamicas: 1/T = ds/de|rho ;  p = rho^2 T ds/drho|e
print("\n== verificacion: recuperar p y T de las derivadas, contra Cantera directo")
print("%12s %12s %10s %10s %10s %10s" % ("rho", "e", "T tabla", "T recup", "p tabla", "p recup"))
err_T, err_p = [], []
rng = np.random.default_rng(0)
for _ in range(8):
    i = rng.integers(2, NR - 2); j = rng.integers(2, NE - 2)
    if np.isnan(S[i, j]):
        continue
    T_rec = 1.0 / dsde[i, j]
    p_rec = -rho_grid[i] ** 2 * T_rec * dsdrho[i, j]   # p = -rho^2 T (ds/drho)_e
    err_T.append(abs(T_rec - T[i, j]) / T[i, j] * 100)
    err_p.append(abs(p_rec - Pm[i, j]) / Pm[i, j] * 100)
    print("%12.4f %12.4e %10.1f %10.1f %10.3e %10.3e"
          % (rho_grid[i], e_grid[j], T[i, j], T_rec, Pm[i, j], p_rec))
print("\nerror medio en T: %.3f %%   en p: %.3f %%" % (np.mean(err_T), np.mean(err_p)))
print("(el error viene de las diferencias finitas; se reduce refinando la malla de la tabla)")
