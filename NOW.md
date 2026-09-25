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
DT=5.0e-8 bash su2/run_from_seed.sh valL3_dt5e8 mesh_L3.su2 su2/seed_L3_from_L1_at_2ms.csv.gz 900 <cores>
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
DT=5.0e-8 bash su2/run_from_seed.sh p2_L3_N2_A_NPR50 mesh_L3.su2 su2/seed_L3_from_L1_at_2ms.csv.gz 30000 <cores>
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

## After L3 finishes - what to do without waiting for an answer

1. Report as usual: check summary and `x_sep` from the throat **averaged over the
   last 0.75 ms**. For reference: L1 = 85.08 mm, L2 = 93.49 mm (same metric).
2. Then compare **L2 vs L3**:
   - **Within 2%** (i.e. |x_sep(L3) - 93.49| <= 1.9 mm): the medium mesh is good
     enough for production. Start the first validation case on L2 and say so in
     your commit message:
     ```
     NPR=20 DT=1.0e-7 bash su2/run_from_seed.sh p3_L2_NPR20 mesh_L2.su2 su2/seed_L2_from_L1_at_2ms.csv.gz 15000 6
     ```
     (that seed is for NPR=50; for NPR=20 it is only a starting guess, so expect a
     longer initial transient - report x_sep over the last 0.75 ms anyway)
   - **Outside 2%**: do NOT start anything else. Report it and stop; the choice
     between running production on L3 or adding a finer level is a project
     decision, not a solver one.
3. If L3 dies or degrades (late median drop below ~0.5), stop and report the step
   number - restarts every 2500 steps mean almost nothing is lost.

The laptop is meanwhile running the time-step study on L2 (dt = 5e-8 against the
finished dt = 1e-7 run), which the spec requires regardless of the mesh verdict.

## 2026-09-24 update - read before launching anything

- **Pull first.** The runner now (a) takes `NPR` (we both added this - merged, yours
  kept), (b) has `DRYRUN=1` to generate the configs without running, and (c) executes
  a **sealed copy** of itself inside the case directory. That last one matters: editing
  the shared script while a job is running made bash re-read it mid-execution and
  re-launch a finished stage. The seal makes that impossible.
- **Time-step study is closed**: on L2, dt=1e-7 vs 5e-8 differ by 0.13% in x_sep and
  0.17% mean in wall pressure. dt=1e-7 is therefore what production cases use.
- **Validation cases changed to NPR 30, 33 and 40 only.** The literature review found
  that at NPR 35 and 37 the experiment is in restricted shock separation (RSS), a
  reattaching topology that a 2D axisymmetric URANS will not reproduce reliably;
  published CFD of this nozzle deliberately restricted itself to FSS for the same
  reason. NPR 30/33/40 are FSS in all sources.
- **Comparison conventions are fixed by the experiment**: wall pressure as p_w/p_a,
  axial coordinate as x/r_t measured from the throat. Use
  `su2/validate_vs_experiment.py RUN_DIR NPR OUTDIR` which applies them and compares
  against the digitized measurements.
- The laptop is running NPR 33. **When L3 finishes, take NPR 30** (seed from the L2
  NPR50 solution if you have it, otherwise report and I will ship a seed):
  ```
  NPR=30 DT=1.0e-7 bash su2/run_from_seed.sh p3_L2_NPR30 mesh_L2.su2 <seed> 25000 <cores>
  ```

## 2026-09-25 - next task for this machine: NPR 33 on L3

L3 is done and settled (x_sep 97.04 mm from throat, constant over the last five
snapshots). Your grid decision was right to stop production, but the three levels
turned out to be in the asymptotic range, so the study is not a failure:

    L1 85.08 -> L2 93.49 -> L3 97.15 mm (from throat)
    apparent order p = 2.29, asymptotic-range check 0.993
    Richardson extrapolation: 99.97 mm, GCI(L2,L3) = 3.6%

That quantified numerical uncertainty replaces the fixed 2% criterion, so no finer
mesh is required for the poster.

**Run the first validation point on the fine mesh:**

```
NPR=33 DT=5.0e-8 bash su2/run_from_seed.sh p3_L3_NPR33 mesh_L3.su2 su2/seed_L3_from_L1_at_2ms.csv.gz 30000 <cores>
```

~24 h on 6 cores. Note dt = 5e-8 (L3 needs it; 1e-7 collapses there) and NPR = 33.

When it finishes, report as usual plus x_sep from the throat averaged over the last
0.75 ms, and run:

```
python3 su2/validate_vs_experiment.py ~/su2-work/p3_L3_NPR33 33 results/p3_L3_NPR33_validation
```

That script compares against the digitized DLR measurements using the experiment's
own conventions (p_w/p_a versus x/r_t from the throat). For reference, the same case
on L2 gave x_sep = 63.8 mm from the throat against 75.65 mm measured; the grid trend
above is expected to close part of that gap.

### Fix for the missing experimental data (2026-09-25)

`validate_vs_experiment.py` had a hard-coded path to a folder that only exists on
the laptop. The digitized DLR measurements are now shipped in the repo under
`data/experiment/`, and the script resolves them relative to `SRC` (or `EXP_CSV`).
`git pull` and run it as:

```
SRC=/path/to/repo python3 su2/validate_vs_experiment.py ~/su2-work/<case> <NPR> results/<case>_validation
```
