# Current instructions - read this after every `git pull`

Updated: 2026-09-30, after your L3 extension and the re-measured y+ landed.

## Your two deliveries: one closes a hole, the other says "not yet"

**y+ on L3: done and it goes straight into the poster.** With the fixed script the plot is a
single branch confined to the nozzle: **y+ ~ 1.3 to 2.6 through the divergent**, peaking near 9
just upstream of the throat. That is the number the poster was missing, and it confirms the
earlier estimate of ~2.6.

**L3 at NPR 33: still not settled.** Your extension gives 72.27 +/- 0.90 mm over the last
quarter, but the second half is still drifting at **+7.2 mm/ms**. For comparison, the L2 record
at the same NPR needed 15 ms to flatten to 0.02 mm/ms. Three milliseconds is not enough on the
fine mesh either.

Do not read that as a wasted run - it is informative. L3 is at 72.3 and **rising**, L2 settled at
62.25, and the measurement is 75.65. So the fine mesh is moving toward the data, exactly as the
grid study predicted. If it settles near the experiment, the campaign's headline stops needing an
extrapolation at all.

## Task: keep L3 going

```bash
git pull
gzip -9 -c ~/su2-work/p7_L3_NPR33_ext/restart_30000.csv > su2/seed_L3_NPR33_at_3ms.csv.gz
NPR=33 DT=5.0e-8 bash su2/run_from_seed.sh p8_L3_NPR33_ext2 mesh_L3.su2 \
    su2/seed_L3_NPR33_at_3ms.csv.gz 60000 <cores>
```

60 000 steps = **3 ms more** (about 2 days at your rate). The EASN poster is 26 October, so there
is room; the value of this run is that it turns the poster's main result from a band into a single
number.

**Report at the halfway point too** (there are restarts every 2500 steps, so you can extract the
series without stopping the run):

```bash
python3 su2/wall_series.py ~/su2-work/p8_L3_NPR33_ext2 5.0e-8 results/series/L3_NPR33_ext2.csv
python3 su2/wall_series_plot.py results/series/L3_NPR33_ext2.csv results/series/L3_NPR33_ext2.png "L3 NPR 33"
```

**Stopping rule, so you do not have to ask:** if the second-half drift falls below **0.5 mm/ms**,
that is settled enough - push the series and say so, and do not start anything else. If it is
still above 3 mm/ms when the run ends, push it anyway and say so; we will decide whether to keep
going or to report L3 as a bounded trend.

## Standing rules

- Health metric: decades of residual drop per physical step (>= 1.2).
- dt per mesh: **L2 -> 1e-7**, **L3 -> 5e-8**.
- AC power, sleep disabled.
- Do not change physics settings.

## Everything else, so you have the picture

- **Poster**: complete A0 draft, one page, in English. Your y+ number closes one of the two gaps;
  this L3 run closes the other.
- **Cloud**: deleted. The queue finished (NPR 30, 40, SA) and the vacuum ramp gave an attached
  reference profile out to x/r_t = 11.3 before diverging, which was enough.
- **Laptop**: hot-gas groundwork for the IAC paper. The tabulated path now runs end to end with a
  real LOX/LH2 equilibrium table (10 000 states, 0.06 % interior error). Two findings worth
  knowing: with a non-ideal fluid SU2 forbids MARKER_OUTLET **and** MARKER_FAR, and it extrapolates
  silently outside the table instead of warning.
