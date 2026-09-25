#!/usr/bin/env python3
"""Phase 1 checks for the SU2 run, same criteria as tools/check_phase1.py.

Snapshots: restart_NNNNN.csv (conservative variables; SU2 8.5 with SST:
Energy = rho*(e + |u|^2/2 + k), CNSVariable.cpp:145).  T = (g-1)/R (E/rho-|u|^2/2-k).
Wall/separation from the node layer next to the nozzle wall, using the Eilmer
block index map written by eilmer_grid_to_su2.py.

usage: check_su2_phase1.py WORKDIR OUTDIR T0 P0 P_AMB
"""
import sys, os, re, glob, csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

W, outdir = sys.argv[1], sys.argv[2]
T0, P0, PA = map(float, sys.argv[3:6])
G, R = 1.4, 296.8
CP = G * R / (G - 1)
CFGS = [f for f in ("stageB.cfg", "B.cfg") if os.path.exists(os.path.join(W, f))]
m = re.search(r"^TIME_STEP=\s*(\S+)", open(os.path.join(W, CFGS[0])).read(), re.M) if CFGS else None
DT = float(m.group(1)) if m else 0.0     # 0 => steady run: the "t" column is meaningless
os.makedirs(outdir, exist_ok=True)
idm = np.load(glob.glob(os.path.join(W, "mesh_L*_idmap.npz"))[0])
NOZ = ["b0", "b1", "b2", "b3"]                      # conv + 3 diverging blocks, wall = north (j=-1)
EILMER_RUN2 = os.path.expanduser("~/eilmer-work/dlr-par/runs/p1_L0_N2_A_NPR50/post/wall-0012.txt")

SRC = os.environ.get("SRC", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
geo = open(os.path.join(SRC, "dlr_par_real_geometry.lua")).read()
pts = np.array([[float(a), float(b)] for a, b in re.findall(r"\{\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\}", geo)])
xw, rw = pts[:, 0], pts[:, 1]
it = int(np.argmin(rw)); x_t, r_t = xw[it], rw[it]; x_ex, r_ex = xw[-1], rw[-1]


def area_mach(ar, sup):
    f = lambda M: (1 / M) * ((2 / (G + 1)) * (1 + (G - 1) / 2 * M * M)) ** ((G + 1) / (2 * (G - 1))) - ar
    lo, hi = (1.0, 50.0) if sup else (1e-6, 1.0)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if (f(lo) > 0) == (f(mid) > 0): lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)


M_is = np.array([area_mach((r / r_t) ** 2, x > x_t) if r > r_t else 1.0 for x, r in zip(xw, rw)])
p_is = P0 * (1 + (G - 1) / 2 * M_is ** 2) ** (-G / (G - 1))
psep = PA * np.clip(1.88 * M_is - 1, 1e-6, None) ** -0.64
ks = np.where((xw > x_t) & (p_is <= psep))[0]
x_schm = xw[ks[0]] if len(ks) else np.nan


def load(f):
    d = np.genfromtxt(f, delimiter=",", names=True)
    rho = d["Density"]; u = d["Momentum_x"] / rho; v = d["Momentum_y"] / rho
    k = d["Turb_Kin_Energy"]
    e = d["Energy"] / rho - 0.5 * (u * u + v * v) - k
    T = (G - 1) / R * e; p = rho * R * T
    order = np.argsort(d["PointID"].astype(int))
    return {n: a[order] for n, a in dict(x=d["x"], y=d["y"], rho=rho, u=u, v=v, T=T, p=p, k=k,
                                          Tt=T + 0.5 * (u * u + v * v) / CP).items()}


def wall(s):
    xs, pw, un = [], [], []
    for b in NOZ:
        ids = idm[b]
        xs += list(s["x"][ids[-1, :]]); pw += list(s["p"][ids[-1, :]]); un += list(s["u"][ids[-2, :]])
    xs, pw, un = map(np.array, (xs, pw, un)); o = np.argsort(xs)
    xs, pw, un = xs[o], pw[o], un[o]
    _, uq = np.unique(xs, return_index=True)             # block-interface duplicates
    return xs[uq], pw[uq], un[uq]


def itnum(f):                      # unsteady: restart_00500.csv ; steady: restart_B.csv
    d = re.findall(r"(\d+)\.csv", f)
    return int(d[0]) if d else -1


snaps = sorted(glob.glob(os.path.join(W, "restart*.csv")), key=itnum)
if DT:
    snaps = [f for f in snaps if itnum(f) % 2500 == 0 or f == snaps[-1]]
rows = []
for f in snaps:
    n = itnum(f); s = load(f); t = n * DT
    nan = int(sum(np.isnan(s[k]).sum() for k in ("rho", "u", "T")))
    inz = (s["x"] <= x_ex + 1e-9) & (s["y"] <= r_ex + 1e-9)
    xs, pw, un = wall(s)
    rev = np.where((xs > x_t + 0.002) & (un < 0))[0]
    xsep = xs[rev[0]] if len(rev) else np.nan
    be = np.nanargmax(np.where(~inz, s["T"], -1))
    rows.append(dict(n=n, t=t, nan=nan, Tn=np.nanmax(s["T"][inz]), Ttn=np.nanmax(s["Tt"][inz]),
                     Te=np.nanmax(s["T"][~inz]), Tte=np.nanmax(s["Tt"][~inz]), xe=s["x"][be], ye=s["y"][be],
                     Tmin=np.nanmin(s["T"]), xsep=xsep, s=s))

last = rows[-1]; s = last["s"]
xs, pw, un = wall(s)
km = np.argmin(np.where(xs > x_t, pw, np.inf)); x_pmin = xs[km]
rises = np.diff(pw[:km + 1]) / pw[:km]
mono_ok = bool(np.all(rises < 0.01))
band = (xs > x_t + 0.005) & (xs < x_t + 0.9 * (x_pmin - x_t))
err = np.abs(pw[band] - np.interp(xs[band], xw, p_is)) / np.interp(xs[band], xw, p_is) * 100
late = [r for r in rows if r["t"] >= 0.5e-3] if DT else rows[-1:]   # steady: judge the final state
WHEN = "after 0.5 ms" if DT else "final state"
T_all_ok = bool(late) and max(max(r["Tn"], r["Te"]) for r in late) <= T0 * 1.001
T_noz_ok = bool(late) and max(r["Tn"] for r in late) <= T0 * 1.001
nan_ok = sum(r["nan"] for r in rows) == 0

L = []; P = L.append
P(f"SU2 PHASE 1 CHECK  work={W}  dt={DT:g} s  NPR={P0/PA:.1f}  T0={T0} K")
P(f"final snapshot: iter {last['n']}  t={last['t']*1e3:.3f} ms")
P(f"[{'PASS' if nan_ok else 'FAIL'}] NaN values: {sum(r['nan'] for r in rows)}")
P(f"[{'PASS' if T_noz_ok else 'FAIL'}] static T <= T0 inside nozzle ({WHEN}): max {max((r['Tn'] for r in late), default=np.nan):.2f} K")
P(f"[{'PASS' if T_all_ok else 'FAIL'}] static T <= T0 whole domain ({WHEN}): max {max((max(r['Tn'], r['Te']) for r in late), default=np.nan):.2f} K")
P(f"[info] total T (T+|u|^2/2cp) max ({WHEN}): nozzle {max((r['Ttn'] for r in late), default=np.nan):.1f} K, external {max((r['Tte'] for r in late), default=np.nan):.1f} K")
P(f"[{'PASS' if np.isfinite(last['xsep']) else 'FAIL'}] separation (first u<0 next to wall): x={last['xsep']*1e3:.2f} mm "
  f"= {(last['xsep']-x_t)*1e3:.2f} mm from throat")
P(f"[{'PASS' if mono_ok else 'FAIL'}] wall p monotonic inlet->p_min (max local rise {rises.max()*100:.2f}%), p_min at x={x_pmin*1e3:.2f} mm")
P(f"[info] wall p vs 1-D isentropic (attached band): mean {np.nanmean(err):.1f}%, max {np.nanmax(err):.1f}%")
P(f"[info] Schmucker x_sep: {x_schm*1e3:.2f} mm = {(x_schm-x_t)*1e3:.2f} mm from throat")
P("")
P("  iter   t[ms]  NaN  Tmax_noz  TtMax_noz  Tmax_ext  TtMax_ext  at(x,r)[m]      Tmin   x_sep[mm]  from_throat[mm]")
for r in rows:
    P(f" {r['n']:5d} {r['t']*1e3:7.3f} {r['nan']:4d} {r['Tn']:9.2f} {r['Ttn']:10.2f} {r['Te']:9.2f} {r['Tte']:10.2f}  "
      f"({r['xe']:.3f},{r['ye']:.3f}) {r['Tmin']:7.1f} {r['xsep']*1e3:10.2f} {(r['xsep']-x_t)*1e3:12.2f}")
txt = "\n".join(L); print(txt)
open(os.path.join(outdir, "su2_phase1_summary.txt"), "w").write(txt + "\n")

# plots: wall pressure SU2 vs Eilmer Run 2 vs isentropic; T history
fig, ax = plt.subplots(1, 2, figsize=(14, 4.8))
ax[0].semilogy((xs - x_t) * 1e3, pw / P0, "r.-", ms=3, label=f"SU2 SST, t={last['t']*1e3:.2f} ms")
if os.path.exists(EILMER_RUN2):
    Lh = [l for l in open(EILMER_RUN2) if l.strip()]
    i0 = next(i for i, l in enumerate(Lh) if l.startswith("pos.x")); h = Lh[i0].split()
    d = np.array([[float(v) for v in l.split()] for l in Lh[i0 + 1:]]); o = np.argsort(d[:, 0])
    ax[0].semilogy((d[o, 0] - x_t) * 1e3, d[o, h.index("p")] / P0, "b.-", ms=3, label="Eilmer k-omega, t=3.00 ms")
ax[0].semilogy((xw - x_t) * 1e3, p_is / P0, "k--", label="1-D isentropic")
ax[0].axhline(PA / P0, color="gray", ls=":", label="p_amb")
ax[0].axvline((x_schm - x_t) * 1e3, color="g", ls=":", label="Schmucker")
if np.isfinite(last["xsep"]): ax[0].axvline((last["xsep"] - x_t) * 1e3, color="r", ls=":", label="SU2 x_sep")
ax[0].set_xlabel("x from throat [mm]"); ax[0].set_ylabel("p_wall/P0"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3, which="both")
t = [r["t"] * 1e3 for r in rows]
ax[1].plot(t, [r["Tn"] for r in rows], "b.-", label="max T nozzle")
ax[1].plot(t, [r["Te"] for r in rows], "r.-", label="max T external")
ax[1].plot(t, [r["Tte"] for r in rows], "m:", label="max total T external")
ax[1].axhline(T0, color="k", ls="--", label="T0"); ax[1].set_xlabel("t [ms]"); ax[1].set_ylabel("K"); ax[1].legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(outdir, "su2_phase1.png"), dpi=130)
print("written", outdir)
