# Current instructions - read this after every `git pull`

Updated: 2026-09-23 morning.

## Settled so far

- **Task A (steady RANS): answered - it does NOT converge.** Your run stalls at
  rms[Rho] ~ -2.6 in first order and goes backwards under MUSCL until NaN at
  iteration ~845. Same outcome as two earlier independent attempts (an older SU2
  campaign stalled at ~1e-2, an Eilmer steady attempt died in its preconditioner).
  Treat this as a result, not a failure: it supports the project's URANS choice.
  **Do not spend more time on steady runs.**
- **The fine-mesh unsteady failures are solved: the physical time step was too
  large.** Neither the pseudo-CFL, nor more inner iterations, nor a stronger
  preconditioner, nor the slope-limiter coefficient fixed it (raising the Venkat
  coefficient made convergence worse). On L3, `dt = 5e-8` sustains ~1.24 decades
  of residual drop per step over 900 steps; `dt = 1e-7` collapses to ~0.3 and dies.

## SWAP (2026-09-23): this machine (desktop) now runs L3, the laptop runs L2

The desktop does not sleep and is faster, so the long fine-mesh run moves here.
**L3 dt is already validated: use dt = 5e-8** (1.24 decades of drop per step over
900 steps; dt=1e-7 collapses and dies - do not use it).

**Step 1 - confirm the settings on YOUR machine before committing ~24 h** (~1 h):

```bash
git pull
bash setup_and_verify.sh            # if you have not run it on this machine
DT=5.0e-8 bash su2/run_from_seed.sh valL3_dt5e8 su2/meshes/mesh_L3.su2 su2/seed_L3_from_L1_at_2ms.csv.gz 900 <cores>
```

Then measure the median decades of rms[Rho] dropped per physical step over the
last 200 steps (inner iteration 0 vs the last inner iteration of each step):

```bash
python3 - ~/su2-work/valL3_dt5e8 <<'PY'
import sys, csv, glob, os
h = glob.glob(os.path.join(sys.argv[1], "history_B*.csv"))[0]
rows = [r for r in csv.reader(open(h))]
hdr = [c.strip().strip('"') for c in rows[0]]
i = [k for k, c in enumerate(hdr) if "rms[Rho]" in c][0]
per = {}
for r in rows[1:]:
    if r: per.setdefault(int(r[0]), []).append(r)
ks = sorted(per)
d = [float(per[s][0][i]) - float(per[s][-1][i]) for s in ks]
late = d[-200:]
print("steps", len(ks), "late median drop", round(sorted(late)[len(late)//2], 2),
      "min", round(min(late), 2))
PY
```

Expected here: ~900 steps, late median ~1.2 decades, no NaN. **If it comes out
below 1.0 or it dies, stop and report - do not start step 2.**

**Step 2 - the full run** (~24 h on 6 cores, less with more):

```bash
DT=5.0e-8 bash su2/run_from_seed.sh p2_L3_N2_A_NPR50 su2/meshes/mesh_L3.su2 su2/seed_L3_from_L1_at_2ms.csv.gz 30000 <cores>
```

Use as many cores as the desktop has (e.g. `8`, `12`). Expect ~24 h on 6 cores,
less if it has more. Restarts every 2500 steps, so an interruption costs ~2 h.
Keep it awake for the whole run.

Report when done (or at any interruption): the check summary and `x_sep` from the
throat **averaged over the last 0.75 ms**. L1 gave 84.8 mm; the laptop is running
L2 for the same comparison.

**The L2 task below is now the laptop's, not yours.** Skip it.

## (laptop) validate dt on L2, then run it

L2 sits between L1 (where dt=1e-7 was fine) and L3 (where it is not), so **do not
assume a value - measure it**, exactly as was done on L3:

```bash
git pull
# 1) two 900-step validations, ~1 h each
DT=1.0e-7 bash su2/run_from_seed.sh valL2_dt1e7 mesh_L2.su2 su2/seed_L2_from_L1_at_2ms.csv.gz 900 6
DT=5.0e-8 bash su2/run_from_seed.sh valL2_dt5e8 mesh_L2.su2 su2/seed_L2_from_L1_at_2ms.csv.gz 900 6
```

For each, report the **median decades of rms[Rho] dropped per physical step over
the last 200 steps** (inner iteration 0 vs the last inner iteration of that step).
Accept the largest dt whose late median stays **>= 1.2 decades** with no NaN.

2) Then run L2 with the accepted dt, 1.5 ms of simulated time:

```bash
DT=<accepted> bash su2/run_from_seed.sh p2_L2_N2_A_NPR50 mesh_L2.su2 \
    su2/seed_L2_from_L1_at_2ms.csv.gz <steps> 6
```
where `<steps> = 1.5e-3 / DT` (30000 for 5e-8, 15000 for 1e-7). Expect 8-16 h.
Restarts are written every 2500 steps, so an interruption costs little.

**Report:** check summary, and `x_sep` from the throat **averaged over the last
0.75 ms** (it oscillates; a single instant is not comparable). The other machine
is running L3 with dt=5e-8 for the same comparison. L1 gave 84.8 mm.

## Standing rules

- The metric that decides whether a run is healthy is **decades of residual drop
  per physical step**, not the residual level. Below ~0.5 and sinking, stop and
  report; do not wait for the NaN.
- Keep the machine on AC power with sleep disabled: on the other machine a
  suspend silently killed a long run twice.
- Do not change physics settings (gas, SST, boundary conditions). Only dt and
  solver controls are open, and only with a measurement behind them.
