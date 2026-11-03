# -*- coding: utf-8 -*-
"""El cabo que faltaba: que gamma efectivo lleva LA TABLA.

La tabla se construyo con equilibrate('TV') en cada punto, asi que deberia llevar la
termodinamica de EQUILIBRIO. Esto lo comprueba sin creerselo: toma la s(rho,e) tabulada,
se mueve a lo largo de una isentropa y calcula gamma_s = (rho/p)(dp/drho)_s, que es el
gamma que de verdad gobierna la expansion en la tobera. Se compara contra Cantera en
equilibrio EN EL MISMO ESTADO y contra el patron de CEA.
"""
import numpy as np
import cantera as ct

RU = ct.gas_constant
TAB = "/mnt/d/eilnerCC/hot/table_rhoe_raw.csv"
d = np.genfromtxt(TAB, delimiter=",", names=True)

rho_u = np.unique(d["Density"])
e_u = np.unique(d["Energy"])
n_r, n_e = len(rho_u), len(e_u)
print("tabla: %d x %d = %d puntos" % (n_r, n_e, len(d)))
print("  rho de %.4e a %.4e kg/m3" % (rho_u.min(), rho_u.max()))
print("  e   de %.4e a %.4e J/kg" % (e_u.min(), e_u.max()))

# reordenar a malla (rho, e)
idx_r = np.searchsorted(rho_u, d["Density"])
idx_e = np.searchsorted(e_u, d["Energy"])
S = np.full((n_r, n_e), np.nan)
P = np.full((n_r, n_e), np.nan)
T = np.full((n_r, n_e), np.nan)
S[idx_r, idx_e] = d["s"]
P[idx_r, idx_e] = d["p"]
T[idx_r, idx_e] = d["T"]
print("  huecos: %d" % np.isnan(S).sum())

def bilineal(M):
    """interpolacion bilineal a mano sobre la malla regular (rho, e)"""
    def f(pts):
        out = []
        for r, e in pts:
            if not (rho_u[0] <= r <= rho_u[-1] and e_u[0] <= e <= e_u[-1]):
                out.append(np.nan); continue
            i = min(np.searchsorted(rho_u, r) - 1, n_r - 2); i = max(i, 0)
            j = min(np.searchsorted(e_u, e) - 1, n_e - 2); j = max(j, 0)
            tr = (r - rho_u[i]) / (rho_u[i + 1] - rho_u[i])
            te = (e - e_u[j]) / (e_u[j + 1] - e_u[j])
            q = M[i:i + 2, j:j + 2]
            out.append((1 - tr) * (1 - te) * q[0, 0] + tr * (1 - te) * q[1, 0]
                       + (1 - tr) * te * q[0, 1] + tr * te * q[1, 1])
        return np.array(out)
    return f


fs, fp, fT = bilineal(S), bilineal(P), bilineal(T)


def e_a_s_fijo(rho, s_obj, e_lo, e_hi):
    """biseccion en e para quedarse sobre la isentropa"""
    for _ in range(80):
        m = 0.5 * (e_lo + e_hi)
        v = fs([[rho, m]])[0]
        if np.isnan(v):
            return np.nan
        if v < s_obj:
            e_lo = m
        else:
            e_hi = m
    return 0.5 * (e_lo + e_hi)


def gamma_tabla(rho0, e0, frac=0.02):
    s0 = fs([[rho0, e0]])[0]
    pr, rr = [], []
    for f in (1 - frac, 1 + frac):
        r = rho0 * f
        e = e_a_s_fijo(r, s0, e_u.min(), e_u.max())
        if np.isnan(e):
            return np.nan, np.nan
        pr.append(fp([[r, e]])[0])
        rr.append(r)
    dpdrho = (pr[1] - pr[0]) / (rr[1] - rr[0])
    p0 = fp([[rho0, e0]])[0]
    return rho0 / p0 * dpdrho, np.sqrt(dpdrho)


# ---------------------------------------------- estado de camara dentro de la tabla
gas = ct.Solution("h2o2.yaml")
comp = "H2:1.0, O2:6.0"


def eq_en(T_, p_):
    g = ct.Solution("h2o2.yaml")
    g.TPY = T_, p_, comp
    g.equilibrate("TP")
    return g


print()
print("=" * 78)
print("GAMMA ISENTROPICO: tabla contra Cantera-equilibrio contra CEA")
print("=" * 78)
print("  %-34s %9s %9s %9s %8s" % ("estado", "tabla", "Cantera", "a_tabla", "dif"))

casos = []
for nombre, T_, p_ in [("camara 100 bar, 3528 K", 3528.5, 100e5),
                       ("CEA 68.95 bar, 3483 K", 3483.35, 68.947304e5),
                       ("expansion media ~20 bar", 2900.0, 20e5),
                       ("expansion baja ~2 bar", 2100.0, 2e5)]:
    g = eq_en(T_, p_)
    rho0 = g.density
    e0 = g.int_energy_mass
    if not (rho_u.min() <= rho0 <= rho_u.max() and e_u.min() <= e0 <= e_u.max()):
        print("  %-34s FUERA DEL DOMINIO DE LA TABLA (rho=%.4f, e=%.4e)"
              % (nombre, rho0, e0))
        continue
    g_tab, a_tab = gamma_tabla(rho0, e0)

    # gamma_s de equilibrio con Cantera, por diferencias finitas sobre la isentropa
    s0 = g.s
    lp = []
    for f in (0.98, 1.02):
        g2 = ct.Solution("h2o2.yaml")
        g2.TPX = g.T, g.P, g.X
        g2.SP = s0, g.P * f
        g2.equilibrate("SP")
        lp.append((np.log(g2.P), np.log(1.0 / g2.density)))
    g_ct = -(lp[1][0] - lp[0][0]) / (lp[1][1] - lp[0][1])

    dif = 100.0 * (g_tab - g_ct) / g_ct
    marca = "OK " if abs(dif) < 2.0 else "<<<"
    print("  %-34s %9.4f %9.4f %9.1f %+7.2f %% %s"
          % (nombre, g_tab, g_ct, a_tab, dif, marca))
    casos.append(abs(dif) < 2.0)

print()
print("  Referencia CEA en camara: gamma_s = 1.1401, a = 1566.3 m/s")
print()
print("  Nota: 'a_tabla' es sqrt(dp/drho)_s de la tabla, o sea la velocidad del sonido")
print("  de EQUILIBRIO, que es la que CEA reporta como SON VEL. La a_congelada de")
print("  Cantera (1602.9) es otra cantidad y por eso salia 2.3 %% arriba en la auditoria.")
print()
print("VEREDICTO TABLA: %d de %d estados dentro de 2 %%" % (sum(casos), len(casos)))
