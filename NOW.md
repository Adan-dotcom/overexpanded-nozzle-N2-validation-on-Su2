# Current instructions - read this after every `git pull`

Updated: 2026-09-30. **The goal of the L3 work has changed. Read this before continuing.**

## Decision: the poster is frozen

The EASN poster is closed at its current content: validated means with quantified numerical
uncertainty. Nothing from the fine-mesh unsteady work goes into it. That is a scope decision,
not a doubt about the results - the unsteady work is deeper and belongs to the IAC paper.

**So the run you are on is no longer about the poster.** Finish it, but the target has moved.

## Why the target moved

Comparing the settled L2 record against your L3 record:

    L2 (settled, 5-15 ms):  x_sep = 62.22 mm,  rms of motion = 0.067 mm
    L3 (1-3 ms):            x_sep = 70.76 mm,  rms of motion = 1.342 mm

**The fine mesh moves 20 times more than the medium one**, with a dominant time scale of
1.1-1.4 ms, i.e. 700-880 Hz - the band of the ~800 Hz peak the DLR measures. The medium mesh
damps the unsteadiness through numerical dissipation; the fine mesh sustains it.

That means the question is no longer "when does x_sep settle". It is **"what is the unsteady
content on the mesh that actually sustains it"**, and that question has a defined answer length:
enough periods to resolve a spectrum.

## Task: take L3 to a 8-10 ms record

Your current run ends at 6 ms of accumulated L3 record. Then continue:

```bash
git pull
gzip -9 -c ~/su2-work/p8_L3_NPR33_ext2/restart_60000.csv > su2/seed_L3_NPR33_at_6ms.csv.gz
NPR=33 DT=5.0e-8 bash su2/run_from_seed.sh p9_L3_NPR33_long mesh_L3.su2 \
    su2/seed_L3_NPR33_at_6ms.csv.gz 80000 <cores>
```

80 000 steps = 4 ms more, reaching **10 ms total**. At your rate that is about 3 days.

**Why 10 ms and not more:** with a 10 ms record the frequency resolution is 100 Hz and a 800 Hz
signal has 8 periods, which is enough to claim a peak. Beyond that the returns fall off fast.
This is a bounded run with a stated purpose, not another open-ended extension.

Report at the end:

```bash
python3 su2/wall_series.py ~/su2-work/p9_L3_NPR33_long 5.0e-8 results/series/L3_NPR33_long.csv
python3 su2/wall_series_plot.py results/series/L3_NPR33_long.csv results/series/L3_NPR33_long.png "L3 NPR 33, 10 ms"
python3 su2/spectra.py results/series/L3_NPR33_long.csv results/series/L3_NPR33_spectrum.png 1.0
```

The last one is the point of the whole exercise: the wall-pressure spectrum on the mesh that
sustains the motion, to compare against the measured ~300 and ~800 Hz.

Push `results/series/*`, `STATUS` and the xsep summary. Not the wall files.

## Standing rules

- Health metric: decades of residual drop per physical step (>= 1.2).
- dt per mesh: **L2 -> 1e-7**, **L3 -> 5e-8**.
- AC power, sleep disabled. Restarts every 2500 steps, so an interruption costs about 2 h.
- Do not change physics settings.

## The other machines

- **Laptop**: IAC groundwork. The tabulated hot-gas path runs end to end with a real LOX/LH2
  equilibrium table. Currently measuring how much the ambient composition affects separation,
  which decides whether we need a multi-species code for the hot case.
- **Cloud**: deleted.
