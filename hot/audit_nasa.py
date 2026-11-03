# -*- coding: utf-8 -*-
"""Comparar la base termodinamica que usamos contra la de NASA Glenn.

La tabla se construyo con `h2o2.yaml` = submecanismo H2/O2 de GRI-Mech 3.0, cuyos
polinomios NASA-7 estan ajustados hasta 3500 K. Nuestra camara a 100 bar sale a
3528 K: 28 K FUERA del rango de ajuste.

Cantera trae `nasa_gas.yaml`, que es la base de NASA Glenn (polinomios NASA-9), la
misma familia de datos que usa CEA y que llega mucho mas arriba. Esto mide cuanto
cambia el estado de camara al cambiar de base, que es lo que decide si hay que
regenerar la tabla.
"""
import numpy as np
import cantera as ct

RU = ct.gas_constant
H_F_LH2, H_F_LOX = -9012.0, -12979.0
MW_H2, MW_O2 = 2.016, 31.998
OF = 6.0
h_mezcla = (1.0 / MW_H2 * H_F_LH2 + OF / MW_O2 * H_F_LOX) / (1.0 + OF) * 1e3
CEA = dict(T=3483.35, M=13.458, gamma_s=1.1401, a=1566.3, rho=3.2038, cstar=2304.288)
ESP = ["H2", "H", "O", "O2", "OH", "H2O", "HO2", "H2O2"]


def fase(archivo):
    """una fase de gas ideal con solo las especies H/O, desde el archivo dado"""
    try:
        esp = [s for s in ct.Species.list_from_file(archivo) if s.name in ESP]
        if len(esp) < len(ESP):
            print("   %s: solo trae %d de las %d especies (%s)"
                  % (archivo, len(esp), len(ESP),
                     ", ".join(sorted(set(ESP) - {e.name for e in esp}))))
            if not esp:
                return None
        return ct.Solution(thermo="ideal-gas", species=esp)
    except Exception as e:
        print("   no se pudo construir desde %s: %s" % (archivo, str(e)[:120]))
        return None


def rango_T(g):
    lo = max(s.thermo.min_temp for s in g.species())
    hi = min(s.thermo.max_temp for s in g.species())
    return lo, hi


def T_llama(g, p):
    lo, hi = 1500.0, 5500.0
    for _ in range(200):
        m = 0.5 * (lo + hi)
        g.TPY = m, p, "H2:1.0, O2:%f" % OF
        g.equilibrate("TP")
        if g.enthalpy_mass < h_mezcla:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def gamma_s(g):
    s0, p0 = g.s, g.P
    lp = []
    for f in (0.98, 1.02):
        g2 = ct.Solution(thermo="ideal-gas", species=g.species())
        g2.TPX = g.T, g.P, g.X
        g2.SP = s0, p0 * f
        g2.equilibrate("SP")
        lp.append((np.log(g2.P), np.log(1.0 / g2.density)))
    return -(lp[1][0] - lp[0][0]) / (lp[1][1] - lp[0][1])


def cstar(gam, R, T):
    return np.sqrt(gam * R * T) / (gam * np.sqrt((2 / (gam + 1)) ** ((gam + 1) / (gam - 1))))


print("=" * 80)
print("BASES TERMODINAMICAS: la nuestra contra la de NASA Glenn")
print("=" * 80)
bases = [("h2o2.yaml", "GRI-Mech 3.0 (la que uso la tabla)"),
         ("nasa_gas.yaml", "NASA Glenn, polinomios NASA-9 (la de CEA)"),
         ("gri30_highT.yaml", "GRI-Mech 3.0 extendido a alta T")]

res = {}
for arch, desc in bases:
    g = fase(arch)
    if g is None:
        continue
    lo, hi = rango_T(g)
    print()
    print("  %s  —  %s" % (arch, desc))
    print("    especies: %d de %d | rango de ajuste comun: %.0f a %.0f K"
          % (g.n_species, len(ESP), lo, hi))

    fila = {"rango": (lo, hi)}
    for etq, p in (("68.947 bar (CEA)", 68.947304e5), ("100 bar (nuestro caso)", 100e5)):
        T = T_llama(g, p)
        g.TPY = T, p, "H2:1.0, O2:%f" % OF
        g.equilibrate("TP")
        gs = gamma_s(g)
        M = g.mean_molecular_weight
        R = RU / M
        fila[etq] = dict(T=T, M=M, rho=g.density, gamma=gs,
                         a=np.sqrt(gs * R * T), cstar=cstar(gs, R, T),
                         fuera=T > hi)
        print("    %-24s T %7.1f K  M %6.3f  gamma_s %6.4f  a %6.1f  c* %6.1f %s"
              % (etq, T, M, gs, np.sqrt(gs * R * T), cstar(gs, R, T),
                 "<<< FUERA DE RANGO" if T > hi else ""))
    res[arch] = fila

print()
print("=" * 80)
print("CONTRA EL PATRON DE CEA (68.947 bar, equilibrio)")
print("=" * 80)
print("  %-18s %9s %9s %9s %9s %9s" % ("base", "T [K]", "M", "gamma_s", "a [m/s]", "c* [m/s]"))
print("  %-18s %9.2f %9.3f %9.4f %9.1f %9.1f" %
      ("CEA", CEA["T"], CEA["M"], CEA["gamma_s"], CEA["a"], CEA["cstar"]))
for arch, _ in bases:
    if arch not in res:
        continue
    r = res[arch]["68.947 bar (CEA)"]
    print("  %-18s %9.2f %9.3f %9.4f %9.1f %9.1f" %
          (arch.replace(".yaml", ""), r["T"], r["M"], r["gamma"], r["a"], r["cstar"]))
print("  %-18s" % "dif vs CEA [%]")
for arch, _ in bases:
    if arch not in res:
        continue
    r = res[arch]["68.947 bar (CEA)"]
    print("  %-18s %+8.2f %+9.2f %+9.2f %+9.2f %+9.2f" %
          (arch.replace(".yaml", ""),
           100 * (r["T"] - CEA["T"]) / CEA["T"],
           100 * (r["M"] - CEA["M"]) / CEA["M"],
           100 * (r["gamma"] - CEA["gamma_s"]) / CEA["gamma_s"],
           100 * (r["a"] - CEA["a"]) / CEA["a"],
           100 * (r["cstar"] - CEA["cstar"]) / CEA["cstar"]))

print()
print("=" * 80)
print("LA PREGUNTA QUE DECIDE: hay que regenerar la tabla?")
print("=" * 80)
if "nasa_gas.yaml" in res and "h2o2.yaml" in res:
    a = res["h2o2.yaml"]["100 bar (nuestro caso)"]
    b = res["nasa_gas.yaml"]["100 bar (nuestro caso)"]
    print("  A 100 bar, GRI-Mech contra NASA Glenn:")
    for k, u in (("T", "K"), ("M", "kg/kmol"), ("gamma", ""), ("a", "m/s"), ("cstar", "m/s")):
        print("    %-8s %12.4f  %12.4f   %+7.2f %%  %s"
              % (k, a[k], b[k], 100 * (a[k] - b[k]) / b[k], u))
    print()
    print("  GRI-Mech extrapola %s a 100 bar (limite %.0f K, llama %.1f K)."
          % ("SI" if a["fuera"] else "NO", res["h2o2.yaml"]["rango"][1], a["T"]))
