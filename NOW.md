# Current instructions - read this after every `git pull`

Updated: 2026-10-08, after your 10 ms L3 campaign closed.

## Your result is the best number of the whole campaign

    L3, NPR 33, settled:   x_sep = 74.69 +/- 0.39 mm,  drift -0.41 mm/ms
    DLR measurement:                   75.65 mm

That is **-1.3 %**, with no extrapolation, no alignment correction, nothing. For contrast, the same
case on the medium mesh gave 62.25 mm (-17.7 %). The fine mesh is simply right.

It also closes a loop: the Richardson extrapolation from L2/L3 predicted between 72.9 and 77.6 mm
depending on the averaging convention, and the directly computed settled value (74.7-75.0) sits
inside that bracket. The verification machinery was telling the truth.

**On the spectrum.** I concatenated your four L3 segments into one 8.5 ms record (they are physically
continuous, each seeded from the previous restart). Using the settled 5.5 ms, df = 182 Hz:
the wall-pressure fluctuation in the interaction region is **rms 6.8e-2 p_a**, against 1.9e-5 in the
attached region and 5.9e-4 on the medium mesh - **two orders of magnitude more than L2**, and now in
the range one expects experimentally. But the spectrum is red: the energy piles up in the lowest
resolved bins, with no distinct peak at 300 or 800 Hz. The honest reading is that the dominant time
scale is at or beyond the limit of a 5.5 ms record, so **resolving those peaks needs a much longer
run** - 20 ms or more, which is about two weeks of your machine. That is a decision for later, not a
task for now.

## Task: NPR 40 on the fine mesh

This is worth more than more spectrum right now. On the medium mesh the error grew with NPR:
**-9 % at NPR 30, -17.7 % at NPR 33, -25.9 % at NPR 40**. We now know that at NPR 33 the fine mesh
removes essentially all of that error. If it does the same at NPR 40 - the worst case - then the
campaign has a fine-mesh validation curve and the "error grows with NPR" worry dies. If it does
*not*, we have found a real limit of the model near the RSS transition, which is just as publishable.

Seed it from your settled NPR 33 solution, which is the closest developed state available:

```bash
git pull
gzip -9 -c ~/su2-work/p9_L3_NPR33_long/restart_80000.csv > su2/seed_L3_NPR33_settled.csv.gz
NPR=40 DT=5.0e-8 bash su2/run_from_seed.sh p10_L3_NPR40 mesh_L3.su2 \
    su2/seed_L3_NPR33_settled.csv.gz 100000 <cores>
```

100 000 steps = 5 ms, about 3.5 days at your rate. Expect a long transient at the start: it has to
travel from NPR 33 to NPR 40, and on L2 that took roughly 4 ms.

**Stopping rule:** the run is done when the drift over the second half falls below **0.5 mm/ms**,
the same criterion that worked here. If at the end it is still above 2 mm/ms, push what you have and
say so - do not start a continuation on your own, we will decide together.

When it finishes:

```bash
python3 su2/wall_series.py ~/su2-work/p10_L3_NPR40 5.0e-8 results/series/L3_NPR40.csv
python3 su2/wall_series_plot.py results/series/L3_NPR40.csv results/series/L3_NPR40.png "L3 NPR 40"
python3 su2/yplus.py ~/su2-work/p10_L3_NPR40 results/series/yplus_L3_NPR40.png
```

Push `results/series/*`, `STATUS` and the xsep summary. Reference value to compare against:
the DLR measurement at NPR 40 is **101.66 mm**.

## Standing rules

- Health metric: decades of residual drop per physical step (>= 1.2).
- dt per mesh: **L2 -> 1e-7**, **L3 -> 5e-8**.
- AC power, sleep disabled. Restarts every 2500 steps.
- Do not change physics settings.

## The other machines

- **Laptop**: finishing the ambient-composition sensitivity test for the hot-gas work (how much the
  separation moves if the surrounding atmosphere is modelled with the wrong molar mass). That number
  decides whether the IAC case needs a multi-species code.
- **Cloud**: deleted.
