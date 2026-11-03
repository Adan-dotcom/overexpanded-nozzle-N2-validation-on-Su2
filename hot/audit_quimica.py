# -*- coding: utf-8 -*-
"""Auditoria de la termoquimica contra NASA CEA.

Patron de oro (NASA CEA via RocketCEA std_examples, LOX/LH2, O/F 6.0, Pc 1000 psia =
68.947 bar, equilibrio, camara):
    T 3483.35 K | M 13.458 kg/kmol | GAMMAs 1.1401 | Cp 2.0951 cal/(g K)
    a 1566.3 m/s | rho 3.2038e-3 g/cc | c* 7560.0 ft/s
    X: H 0.03417, HO2 0.00003, H2 0.24832, H2O 0.66590, H2O2 0.00001,
       O 0.00334, OH 0.04478, O2 0.00345

Lo que se audita:
  A. Que el mecanismo tenga las mismas especies que CEA.
  B. Que Cantera reproduzca CEA EN LAS CONDICIONES DE CEA (con T de llama CALCULADA,
     no impuesta). Esta es la prueba que valida el motor.
  C. De donde sale el gamma 1.19 del STATE.md y por que CEA dice 1.1401.
  D. La temperatura de camara a 100 bar, calculada en vez de impuesta.
  E. La viscosidad y el ajuste de Sutherland del caso caliente.
"""
import sys

import numpy as np
import cantera as ct

CAL = 4184.0                      # J por kcal/kg -> cal/(g K) a J/(kg K): x4184
RU = ct.gas_constant              # J/(kmol K)

CEA = dict(T=3483.35, M=13.458, gamma_s=1.1401, cp_cal=2.0951, a=1566.3,
           rho=3.2038, cstar_fts=7560.0, p_bar=68.947304, OF=6.0)
CEA["cstar"] = CEA["cstar_fts"] * 0.3048
CEA["cp"] = CEA["cp_cal"] * CAL
CEA_X = {"H": 0.03417, "HO2": 0.00003, "H2": 0.24832, "H2O": 0.66590,
         "H2O2": 0.00001, "O": 0.00334, "OH": 0.04478, "O2": 0.00345}


def dif(mio, ref):
    return 100.0 * (mio - ref) / ref


def linea(nombre, mio, ref, unidad="", tol=1.0):
    d = dif(mio, ref)
    marca = "OK " if abs(d) <= tol else "<<<"
    print("  %-26s %12.4f  %12.4f  %+7.2f %%  %s %s"
          % (nombre, mio, ref, d, marca, unidad))
    return abs(d) <= tol


# ============================================================ A. especies
print("=" * 78)
print("A. ESPECIES DEL MECANISMO contra las que lista CEA")
print("=" * 78)
gas = ct.Solution("h2o2.yaml")
mec = set(gas.species_names)
cea = set(CEA_X)
print("  mecanismo h2o2.yaml (%d especies): %s" % (gas.n_species, sorted(mec)))
print("  CEA lista (%d): %s" % (len(cea), sorted(cea)))
faltan = cea - mec
sobran = mec - cea
print("  faltan del mecanismo : %s" % (sorted(faltan) if faltan else "ninguna"))
print("  extra en el mecanismo: %s" % (sorted(sobran) if sobran else "ninguna"))
if faltan:
    print("  <<< FALLA: el mecanismo no puede formar especies que CEA si forma.")
else:
    print("  OK  el mecanismo cubre todas las especies de equilibrio de CEA.")

# ====================================== B. reproducir CEA con T de llama CALCULADA
print()
print("=" * 78)
print("B. CANTERA contra CEA, en las condiciones de CEA (68.947 bar, O/F 6.0)")
print("   La temperatura se CALCULA resolviendo HP desde los propulsantes.")
print("=" * 78)

# Propulsantes: H2 y O2 entran al inyector. CEA usa por defecto los reactivos
# criogenicos en su punto de ebullicion; el h2o2.yaml solo tiene gas ideal, asi que
# se entra con los gases a 20.3 K (LH2) y 90.2 K (LOX) seria extrapolar los
# polinomios NASA fuera de rango. Se hace el balance de entalpia a mano:
# h_mezcla = (Y_H2 h_H2(T_H2) + Y_O2 h_O2(T_O2)), usando para cada uno la entalpia
# de formacion del liquido tabulada por CEA.
H_F_LH2 = -9012.0      # J/mol, entalpia del H2 liquido a 20.27 K (CEA: -2154 cal/mol)
H_F_LOX = -12979.0     # J/mol, entalpia del O2 liquido a 90.17 K (CEA: -3102 cal/mol)
MW_H2, MW_O2 = 2.016, 31.998

OF = CEA["OF"]
m_O2, m_H2 = OF, 1.0
n_O2, n_H2 = m_O2 / MW_O2, m_H2 / MW_H2
H_total = n_H2 * H_F_LH2 + n_O2 * H_F_LOX          # J por (1 + OF) gramos
h_mezcla = H_total / (m_H2 + m_O2) * 1e3           # J/kg

# --- B1: el estado de camara de CEA, sin depender de mis entalpias de liquido.
#     Se impone T y p DE CEA y se compara la composicion y las propiedades. Esto
#     valida los datos termodinamicos y el solver de equilibrio por si solos.
gas.TPY = CEA["T"], CEA["p_bar"] * 1e5, "H2:%f, O2:%f" % (m_H2, m_O2)
gas.equilibrate("TP")

# --- B2 (abajo): la T de llama calculada por biseccion, prueba independiente.
def T_de_llama(h_obj, p, comp, lo=1500.0, hi=5000.0):
    """Biseccion en T: equilibrate('TP') y se busca h_eq(T) = h_obj.
    El HP directo desde un estado frio no converge (ya nos paso antes)."""
    g = ct.Solution("h2o2.yaml")
    for _ in range(200):
        m = 0.5 * (lo + hi)
        g.TPY = m, p, comp
        g.equilibrate("TP")
        if g.enthalpy_mass < h_obj:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


comp = "H2:%f, O2:%f" % (m_H2, m_O2)
T_llama = T_de_llama(h_mezcla, CEA["p_bar"] * 1e5, comp)
print("  entalpia de los propulsantes: %.4e J/kg" % h_mezcla)
print("  T de llama CALCULADA por biseccion: %.1f K  (CEA: %.2f K, dif %+.2f %%)"
      % (T_llama, CEA["T"], dif(T_llama, CEA["T"])))
print("  [las filas de abajo se evaluan en la T y p DE CEA, no en la calculada]")
print()
print("  %-26s %12s  %12s  %9s" % ("cantidad", "Cantera", "CEA", "dif"))
ok = []
ok.append(linea("T de llama calculada [K]", T_llama, CEA["T"], tol=1.0))
ok.append(linea("M [kg/kmol]", gas.mean_molecular_weight, CEA["M"], tol=0.5))
ok.append(linea("rho [kg/m3]", gas.density, CEA["rho"], tol=1.5))
ok.append(linea("a congelada [m/s]", gas.sound_speed, CEA["a"], tol=2.0))

print()
print("  composicion molar:")
for sp in sorted(CEA_X, key=lambda s: -CEA_X[s]):
    x = gas.X[gas.species_index(sp)]
    ref = CEA_X[sp]
    d = dif(x, ref) if ref > 1e-6 else float("nan")
    print("    %-6s %10.5f  %10.5f  %+8.2f %%" % (sp, x, ref, d))

# ====================================== C. el gamma: congelado contra equilibrio
print()
print("=" * 78)
print("C. EL GAMMA: de donde sale 1.19 y por que CEA dice 1.1401")
print("=" * 78)
cp_fro = gas.cp_mass
cv_fro = gas.cv_mass
g_fro = cp_fro / cv_fro
R_mezcla = RU / gas.mean_molecular_weight
print("  Congelado (composicion fija, lo que calcula cp/cv de Cantera):")
print("    cp = %.1f J/(kg K)   cv = %.1f   ->  gamma_congelado = %.4f"
      % (cp_fro, cv_fro, g_fro))
print("    R de la mezcla = %.1f J/(kg K)" % R_mezcla)

# gamma isentropico de EQUILIBRIO: -(dln p/dln v)_s, por diferencias finitas
s0, T0_, p0_ = gas.s, gas.T, gas.P
eps = 0.01
pr = []
for f in (1 - eps, 1 + eps):
    g2 = ct.Solution("h2o2.yaml")
    g2.TPX = gas.T, gas.P, gas.X
    g2.SP = s0, p0_ * f
    g2.equilibrate("SP")
    pr.append((np.log(g2.P), np.log(1.0 / g2.density)))
gamma_s = -(pr[1][0] - pr[0][0]) / (pr[1][1] - pr[0][1])

# cp de equilibrio: dh/dT a p constante, con la composicion reajustandose
hs = []
for dT in (-5.0, 5.0):
    g2 = ct.Solution("h2o2.yaml")
    g2.TPX = gas.T + dT, gas.P, gas.X
    g2.equilibrate("TP")
    hs.append((g2.T, g2.enthalpy_mass))
cp_eq = (hs[1][1] - hs[0][1]) / (hs[1][0] - hs[0][0])

print()
print("  Equilibrio (la composicion se reajusta, que es lo que reporta CEA):")
ok.append(linea("gamma_s equilibrio", gamma_s, CEA["gamma_s"], tol=1.0))
ok.append(linea("cp equilibrio [J/kg K]", cp_eq, CEA["cp"], tol=3.0))
print()
print("  >>> El 1.19 del STATE.md es el gamma CONGELADO (%.4f aqui)." % g_fro)
print("      CEA reporta el ISENTROPICO DE EQUILIBRIO (%.4f). No se contradicen:" % gamma_s)
print("      son dos cantidades distintas. Lo que importa es cual usa la tabla.")

# c* con las dos convenciones
def cstar(g, R, T):
    return np.sqrt(g * R * T) / (g * np.sqrt((2 / (g + 1)) ** ((g + 1) / (g - 1))))


print()
print("  c* con cada convencion:")
ok.append(linea("c* con gamma_s equil [m/s]", cstar(gamma_s, R_mezcla, gas.T),
                CEA["cstar"], tol=2.0))
linea("c* con gamma congelado", cstar(g_fro, R_mezcla, gas.T), CEA["cstar"], tol=2.0)

# ====================================== D. la camara a 100 bar, calculada
print()
print("=" * 78)
print("D. LA CAMARA DE NUESTRO CASO: 100 bar, T CALCULADA (no impuesta)")
print("=" * 78)
T100 = T_de_llama(h_mezcla, 100e5, comp)
g100 = ct.Solution("h2o2.yaml")
g100.TPY = T100, 100e5, comp
g100.equilibrate("TP")
print("  T de llama a 100 bar, O/F 6.0 : %.1f K" % T100)
print("  T que impuso la campana        : 3500.0 K")
print("  diferencia                     : %+.1f K  (%+.2f %%)"
      % (3500.0 - T100, dif(3500.0, T100)))
print("  M = %.3f kg/kmol | R = %.1f J/(kg K) | rho = %.4f kg/m3"
      % (g100.mean_molecular_weight, RU / g100.mean_molecular_weight, g100.density))
print()
print("  Si |dif| < 1 %% la tabla se construyo practicamente en el estado correcto.")

# ====================================== E. viscosidad y Sutherland
print()
print("=" * 78)
print("E. VISCOSIDAD: los valores que usa hot_smoke_test.sh")
print("=" * 78)
T_tab = np.array([300., 1000., 2000., 3500.])
MU_HARD = np.array([1.054e-5, 3.560e-5, 6.607e-5, 1.022e-4])
print("  %8s %14s %14s %9s" % ("T [K]", "Cantera", "en el script", "dif"))
mus = []
for T, mh in zip(T_tab, MU_HARD):
    gv = ct.Solution("h2o2.yaml")
    gv.TPX = T, 100e5, g100.X          # composicion de camara congelada
    gv.equilibrate("TP")
    mus.append(gv.viscosity)
    print("  %8.0f %14.4e %14.4e %+8.2f %%" % (T, gv.viscosity, mh, dif(gv.viscosity, mh)))
mus = np.array(mus)

best = None
for S in np.arange(10., 1200., 1.):
    shape = (T_tab / 300.0) ** 1.5 * (300.0 + S) / (T_tab + S)
    muref = np.sum(mus * shape) / np.sum(shape ** 2)
    err = np.max(np.abs(muref * shape - mus) / mus)
    if best is None or err < best[0]:
        best = (err, muref, S)
print("  mejor Sutherland sobre los valores de Cantera: mu_ref=%.4e S=%.0f, error max %.2f %%"
      % (best[1], best[2], best[0] * 100))

print()
print("=" * 78)
print("VEREDICTO: %d de %d comprobaciones numericas dentro de tolerancia"
      % (sum(ok), len(ok)))
print("=" * 78)
sys.exit(0 if all(ok) else 1)
