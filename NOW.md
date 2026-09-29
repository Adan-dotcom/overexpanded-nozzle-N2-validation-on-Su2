# Current instructions - read this after every `git pull`

Updated: 2026-09-29, after your 15 ms record landed.

## Your 15 ms record: excellent, and it settles two questions at once

    x_sep = 62.25 +/- 0.04 mm over the second half, slope +0.02 mm/ms

Completely settled. For comparison, the 2.5 ms version of the same case was still drifting at
-11.6 mm/ms, and the value we had been quoting was off by ~15%. That single number is now the
anchor for the whole campaign.

The second thing it settles is less comfortable and more interesting. With 13 ms of usable
signal at 200 kHz we computed the wall-pressure spectrum (`su2/spectra.py`):

    x/r_t = 7.35 (interaction)   rms of fluctuation = 5.9e-4 p_a
    x/r_t = 8.14 (downstream)    rms of fluctuation = 4.7e-4 p_a
    x/r_t = 4.95 (attached)      rms of fluctuation = 1.4e-8 p_a

The separated region does fluctuate, four orders of magnitude above the attached region, so the
solver is not simply frozen. But the level is tiny and the spectrum is smooth and red: **no
discrete peak appears near the measured ~300 Hz and ~800 Hz**. The honest reading is that a 2-D
axisymmetric URANS does not sustain the shock oscillation the experiment measures - which is
exactly why the literature uses 3-D DES for side loads. That is a reportable negative result,
not a failure of the run.

## Task 0 (5 minutes): re-run the y+ measurement - my script had a bug

Your `yplus_L3.png` shows two branches reaching x/r_t = 52, but the nozzle ends at 12.5. The
script was looping over **all nine blocks** of the idmap, and only `b0..b3` are the nozzle wall;
`b4..b8` are the ambient region. Fixed and pushed. Verified: on the NPR 50 cases it now
reproduces the campaign values exactly (L0 63.33, L1 20.34, L2 9.71), which confirms those
numbers were right and only the L3 plot was contaminated.

```bash
git pull
python3 su2/yplus.py ~/su2-work/p3_L3_NPR33 results/series/yplus_L3.png
git add results/series && git commit -m "re-measured y+ on L3 with the fixed script" && git push
```

From the lower branch of your contaminated plot, L3 should land near y+ = 1-3 inside the nozzle.
Report median, p95 and max; that number goes straight into the poster, which currently says
"being measured".

## Task 1 (superseded by Task 0): measure y+ on L3

We never measured it on the fine mesh - the poster currently says "estimated". New script,
validated against the known L2 value (it reproduces 9.9 where we had measured 9.7):

```bash
git pull
python3 su2/yplus.py ~/su2-work/p3_L3_NPR33 results/series/yplus_L3.png
git add results/series && git commit -m "measured y+ on L3" && git push
```

Report the median, p95 and max it prints.

## Task 2 (~24 h): settle L3 at NPR 33

This is now the single biggest source of uncertainty in the headline result. The grid-correction
factor we use to extrapolate x_sep is somewhere between 1.14 and 1.24 depending on which
averaging convention is used, and that spread exists because **L3 is not settled**: its record
still drifts at +5.5 mm/ms. L2 is now settled, so L3 is the missing half of the pair.

Continue it from its own last restart:

```bash
gzip -9 -c ~/su2-work/p3_L3_NPR33/restart_30000.csv > su2/seed_L3_NPR33_at_1p5ms.csv.gz
NPR=33 DT=5.0e-8 bash su2/run_from_seed.sh p7_L3_NPR33_ext mesh_L3.su2 \
    su2/seed_L3_NPR33_at_1p5ms.csv.gz 30000 <cores>
```

30000 steps at 5e-8 = 1.5 ms more. If x_sep is still drifting at the end, say so and we will
continue again rather than quote a moving number.

When it finishes:

```bash
python3 su2/wall_series.py ~/su2-work/p7_L3_NPR33_ext 5.0e-8 results/series/L3_NPR33_ext.csv
python3 su2/wall_series_plot.py results/series/L3_NPR33_ext.csv results/series/L3_NPR33_ext.png "L3 NPR 33 settled"
python3 su2/yplus.py ~/su2-work/p7_L3_NPR33_ext results/series/yplus_L3_settled.png
```

Push `results/series/*`, `STATUS` and `xsep_last_0p75ms.txt`. Not the wall files.

## Standing rules

- Health metric: **decades of residual drop per physical step** (>= 1.2). Below ~0.5 and sinking:
  stop and report.
- dt per mesh: **L2 -> 1e-7**, **L3 -> 5e-8**.
- AC power, sleep disabled.
- Do not change physics settings. Only dt and solver controls, with a measurement behind them.

## State of the other machines

- **Cloud: gone.** The queue finished (NPR 30, NPR 40, SA), the vacuum ramp got NPR 100 fully
  converged and NPR 200 attached out to x/r_t = 11.3 before diverging - enough to serve as the
  attached reference profile. Everything was downloaded and the server was deleted, so it is no
  longer costing anything.
- **Laptop:** running the SA extension at NPR 50 (SST vs SA cross-check). SST gives 93.5 mm and
  SA 105.5 mm on the same mesh: **+12.9%**, which is 3.5x the grid uncertainty. Model choice
  dominates every other error source we have quantified.
