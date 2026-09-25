#!/usr/bin/env python3
"""Compare a finished SU2 case against the digitized DLR cold-flow measurements.

Uses the experiment's own conventions (Verma & Haidn and related DLR sources):
  - wall pressure normalized by AMBIENT pressure, p_w/p_a
  - axial coordinate as x/r_throat measured FROM THE THROAT
  - two separation metrics, kept distinct as the experiment does:
      X_sep : physical separation, zero wall shear. Here: the first zero crossing
              of the near-wall axial velocity, linearly interpolated (sub-cell).
      X_inc : incipient separation, where the wall pressure first departs from the
              undisturbed (vacuum-like) profile. Threshold-based, so the value is
              reported for three thresholds to show its sensitivity.
Simulation profiles are averaged over the last snapshots (the flow oscillates;
the experiment reports means over a multi-second hold).

NOTE on X_inc: the experiment measures it against the *vacuum* (fully attached)
wall-pressure profile. A 1-D isentropic profile is NOT a valid substitute for this
TOP nozzle - strong throat curvature and the internal shock make the wall pressure
depart from quasi-1D theory well upstream of any separation. Pass a reference
profile (REF_CSV with columns x_rt,pw_pa from a fully attached high-NPR run) to get
a defensible X_inc; without it, X_inc is printed only as a 1-D-based lower bound
and must not be compared with the experiment.

usage: validate_vs_experiment.py RUN_DIR NPR OUTDIR [N_SNAPSHOTS_AVG] [REF_CSV]
"""
import sys, os, re, glob
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUN, NPR, OUT = sys.argv[1], float(sys.argv[2]), sys.argv[3]
NAVG = int(sys.argv[4]) if len(sys.argv) > 4 else 4
REF = sys.argv[5] if len(sys.argv) > 5 else None
G, R, PA = 1.4, 296.8, 101325.0
# digitized DLR measurements: shipped in the repo, overridable with EXP_CSV
SRC_DIR = os.environ.get("SRC", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXP = os.environ.get("EXP_CSV", os.path.join(SRC_DIR, "data", "experiment", "published_pressure_profiles.csv"))
if not os.path.exists(EXP):
    alt = ("/mnt/d/eilnerCC/PRUEBA SU2_2026/raptor_like_study/cases/"
           "cold_n2_validation/results/published_pressure_profiles.csv")
    if os.path.exists(alt):
        EXP = alt
    else:
        raise SystemExit(f"experimental data not found at {EXP} (set EXP_CSV to its path)")
os.makedirs(OUT, exist_ok=True)

geo = open(os.path.join(SRC_DIR, "dlr_par_real_geometry.lua")).read()
pts = np.array([[float(a), float(b)] for a, b in
                re.findall(r"\{\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\}", geo)])
xw, rw = pts[:, 0], pts[:, 1]
it = int(np.argmin(rw)); x_t, r_t = xw[it], rw[it]

idm = np.load(glob.glob(os.path.join(RUN, "mesh_L*_idmap.npz"))[0])
NOZ = ["b0", "b1", "b2", "b3"]


def load(f):
    d = np.genfromtxt(f, delimiter=",", names=True)
    o = np.argsort(d["PointID"].astype(int)); d = d[o]
    rho = d["Density"]; u = d["Momentum_x"] / rho; v = d["Momentum_y"] / rho
    T = (G - 1) / R * (d["Energy"] / rho - 0.5 * (u * u + v * v) - d["Turb_Kin_Energy"])
    return d["x"], d["y"], rho * R * T, u


def wall_profile(f):
    x, y, p, u = load(f)
    xs, pw, un = [], [], []
    for b in NOZ:
        ids = idm[b]
        xs += list(x[ids[-1]]); pw += list(p[ids[-1]]); un += list(u[ids[-2]])
    xs, pw, un = map(np.array, (xs, pw, un))
    o = np.argsort(xs); xs, pw, un = xs[o], pw[o], un[o]
    _, q = np.unique(xs, return_index=True)
    return xs[q], pw[q], un[q]


snaps = sorted(glob.glob(os.path.join(RUN, "restart_*.csv")),
               key=lambda f: int(re.findall(r"(\d+)\.csv", f)[0]))
snaps = [f for f in snaps if int(re.findall(r"(\d+)\.csv", f)[0]) % 2500 == 0][-NAVG:]
if not snaps:
    raise SystemExit(f"no snapshots in {RUN}")
P, U = [], []
for f in snaps:
    xs, pw, un = wall_profile(f)
    P.append(pw); U.append(un)
pw = np.mean(P, axis=0); un = np.mean(U, axis=0)
pw_sd = np.std(P, axis=0)
xrt = (xs - x_t) / r_t                      # experiment's abscissa
pwa = pw / PA                               # experiment's ordinate


def x_sep_zero_crossing(xrt, un):
    """first sign change of near-wall u downstream of the throat, interpolated"""
    m = xrt > 0.2
    xx, uu = xrt[m], un[m]
    for i in range(len(uu) - 1):
        if uu[i] > 0 >= uu[i + 1]:
            return xx[i] + (xx[i + 1] - xx[i]) * uu[i] / (uu[i] - uu[i + 1])
    return np.nan


def area_mach(ar, sup):
    f = lambda M: (1 / M) * ((2 / (G + 1)) * (1 + (G - 1) / 2 * M * M)) ** ((G + 1) / (2 * (G - 1))) - ar
    lo, hi = (1.0, 50.0) if sup else (1e-6, 1.0)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if (f(lo) > 0) == (f(mid) > 0): lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)


M_is = np.array([area_mach((r / r_t) ** 2, x > x_t) if r > r_t else 1.0 for x, r in zip(xw, rw)])
p_is = (NPR * PA) * (1 + (G - 1) / 2 * M_is ** 2) ** (-G / (G - 1))   # undisturbed profile
p_is_at = np.interp(xs, xw, p_is) / PA
if REF:                      # fully attached reference profile (preferred)
    r = np.genfromtxt(REF, delimiter=",", names=True)
    ref_at = np.interp((xs - x_t) / r_t, r["x_rt"], r["pw_pa"])
else:
    ref_at = p_is_at


def x_inc(thr):
    m = xrt > 0.2
    xx, ratio = xrt[m], (pwa / p_is_at)[m]
    for i in range(len(ratio) - 1):
        if ratio[i] < thr <= ratio[i + 1]:
            return xx[i] + (xx[i + 1] - xx[i]) * (thr - ratio[i]) / (ratio[i + 1] - ratio[i])
    return np.nan


xs_sep = x_sep_zero_crossing(xrt, un)
xincs = {t: x_inc(t) for t in (1.05, 1.10, 1.20)}

# experimental profile for this NPR (start-up branch)
exp = np.genfromtxt(EXP, delimiter=",", names=True, dtype=None, encoding="utf-8")
sel = (exp["sweep_direction"] == "startup") & (np.abs(exp["npr"] - NPR) < 0.5)
L = []; Pr = L.append
Pr(f"VALIDATION vs DLR cold-flow data   run={os.path.basename(RUN)}  NPR={NPR:g}")
Pr(f"averaged over {len(snaps)} snapshots: {[os.path.basename(s) for s in snaps]}")
Pr(f"conventions: p_w/p_a vs x/r_t from throat (r_t={r_t*1e3:.1f} mm, p_a={PA:.0f} Pa)")
Pr("")
Pr(f"X_sep (zero crossing of near-wall u)      : {xs_sep:.3f} x/r_t")
for t, v in xincs.items():
    Pr(f"X_inc (p_w exceeds reference by {int((t-1)*100):3d}%)   : {v:.3f} x/r_t")
if not REF:
    Pr("  WARNING: no attached reference profile given, so X_inc above is computed")
    Pr("  against 1-D isentropic theory, which is invalid for a TOP nozzle near the")
    Pr("  throat. Do not compare these X_inc values with the experiment.")
if sel.any():
    xe = exp["x_rt"][sel]; pe = exp["pwall_over_pa"][sel]
    o = np.argsort(xe); xe, pe = xe[o], pe[o]
    sim_at = np.interp(xe, xrt, pwa)
    err = (sim_at - pe) / pe * 100
    Pr("")
    Pr(f"comparison at the {len(xe)} measured stations:")
    Pr("   x/r_t    p_w/p_a exp   sim     err[%]   sim scatter over snapshots")
    for a, b, c, e in zip(xe, pe, sim_at, err):
        sd = np.interp(a, xrt, pw_sd / PA)
        Pr(f" {a:7.3f} {b:12.4f} {c:8.4f} {e:8.2f}     +/-{sd:.4f}")
    Pr("")
    Pr(f"mean |error| = {np.mean(np.abs(err)):.2f}%   max |error| = {np.max(np.abs(err)):.2f}%")
    Pr(f"(spec target: <5% good, <10% acceptable with explanation)")
else:
    Pr("")
    Pr(f"no start-up experimental profile at NPR={NPR:g} in the digitized data "
       f"(available: {sorted(set(exp['npr'][exp['sweep_direction']=='startup']))})")
txt = "\n".join(L); print(txt)
open(os.path.join(OUT, "validation_summary.txt"), "w").write(txt + "\n")

fig, ax = plt.subplots(figsize=(9, 5.5))
ax.semilogy(xrt, pwa, "b-", lw=1.5, label="SU2 URANS SST (time-averaged)")
ax.fill_between(xrt, (pw - pw_sd) / PA, (pw + pw_sd) / PA, color="b", alpha=.2,
                label="scatter over snapshots")
ax.semilogy(xrt, ref_at, "k--", lw=1, label="reference (attached)" if REF else "1-D isentropic (not a valid reference here)")
if sel.any():
    ax.semilogy(xe, pe, "ro", ms=5, label="DLR experiment (digitized)")
ax.axhline(1.0, color="gray", ls=":", lw=1, label="$p_a$")
if np.isfinite(xs_sep): ax.axvline(xs_sep, color="b", ls=":", lw=1, label="$X_{sep}$ (sim)")
ax.set_xlabel("$x/r_t$ from throat"); ax.set_ylabel("$p_w/p_a$")
ax.set_title(f"Wall pressure, NPR = {NPR:g}"); ax.legend(fontsize=8); ax.grid(alpha=.3, which="both")
ax.set_xlim(0, (xw[-1] - x_t) / r_t)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "wall_pressure_vs_experiment.png"), dpi=130)
print("written", OUT)
