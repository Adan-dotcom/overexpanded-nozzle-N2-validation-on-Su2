# Current instructions - read this after every `git pull`

Updated: 2026-09-26, after your L3 NPR33 run landed.

## Your L3 NPR33 result: accepted, and it is the best number of the campaign

x_sep = 68.96 mm from the throat against **75.65 mm measured** -> **-8.8%**, where the same
case on L2 gave 63.8 mm (-15.7%). Grid refinement moved the separation toward the experiment,
exactly as the NPR 50 grid study predicted. Wall pressure in the attached region sits at ~-10%,
the same near-uniform bias that a +4 to +5 mm rigid axial shift removes (it drops to ~2.5%);
that shift is now confirmed independently at NPR 30 and NPR 33, so it is a single geometric
constant, not a fudge.

## What we learned from your run's `wall_*.csv` files (important)

SU2 writes `wall_<step>.csv` every 50 steps. Those are 30 KB each and we had been ignoring
them, looking only at the 2500-step restarts. That is a sampling rate of **213 kHz** we already
paid for, against the 4 kHz we were actually using.

Extracting the dense series from the laptop's L2 NPR33 run shows the shock foot does **not**
oscillate over the record: it relaxes from the seed (94 -> 65 -> 73 -> 62 mm) and is still
drifting at **-11.6 mm/ms** during the window we were averaging over. In other words, our
reported x_sep values are partly transient, and their uncertainty is window-dependent.

Everything needed to see this is in `su2/wall_series.py` and `su2/wall_series_plot.py`
(see `results/series/L2_NPR33.png` for the output).

**First, cheap task (~5 min): do the same for your finished L3 run and push the result.**

```bash
git pull
python3 su2/wall_series.py ~/su2-work/p3_L3_NPR33 5.0e-8 results/series/L3_NPR33.csv
python3 su2/wall_series_plot.py results/series/L3_NPR33.csv results/series/L3_NPR33.png "L3 NPR 33"
git add results/series && git commit -m "dense wall series of L3 NPR33" && git push
```

Both files are small. Report the printed numbers (mean/std over the last quarter, and the
slope over the second half).

## Main task: the long record for the spectra (~40 h)

This is the last item promised in the accepted EASN abstract that nobody is running. It needs
**record length**, not a higher sampling rate - the sampling is already 200x what we need.

Run NPR 33 on **L2** (not L3: at dt=5e-8 a 10 ms record would be ~160 h, which does not fit),
seeded from the **already-relaxed** 2.5 ms solution so the whole new record is usable:

```bash
NPR=33 DT=1.0e-7 bash su2/run_from_seed.sh spec_L2_NPR33 mesh_L2.su2 \
    su2/seed_L2_NPR33_at_2p5ms.csv.gz 100000 <cores>
```

- 100 000 steps at dt = 1e-7 = **10 ms** of signal -> df = 100 Hz, enough to separate the
  measured ~300 Hz and ~800 Hz peaks. Expect ~40 h on 6 cores.
- If the machine can stay up longer, **150 000 steps (15 ms) is materially better** for the
  spectral statistics. Your call based on how long you can keep it undisturbed.
- Disk: ~2000 `wall_*.csv` files, ~70 MB total, plus restarts every 2500 steps. Fine.
- Do **not** lower the output frequency. The wall files are what the whole exercise is for.

When it finishes (or at any interruption):

```bash
python3 su2/wall_series.py ~/su2-work/spec_L2_NPR33 1.0e-7 results/series/spec_L2_NPR33.csv
python3 su2/wall_series_plot.py results/series/spec_L2_NPR33.csv results/series/spec_L2_NPR33.png "L2 NPR 33, 10 ms"
```

and push **only** `results/series/*` plus `STATUS` and `xsep_last_0p75ms.txt` - not the 2000
wall files, they stay on your disk until we decide what else to extract.

## Standing rules

- Health metric is **decades of residual drop per physical step** (>= 1.2). Below ~0.5 and
  sinking: stop and report, do not wait for the NaN.
- dt is validated per mesh: **L2 -> 1e-7**, **L3 -> 5e-8**. Do not mix them up.
- AC power, sleep disabled. A suspend has silently killed a long run twice.
- Do not change physics settings (gas, SST, boundary conditions). Only dt and solver controls,
  and only with a measurement behind them.

## State of the other machines

- **Cloud (Hetzner):** running the queue - NPR 30 done and collected, NPR 40 running now, then
  SA at NPR 50, then NPR 200 for the vacuum profile. Delete protection is ON, so nothing will
  remove that server automatically; it gets deleted by hand once results are collected.
- **Laptop:** free, analysis only.
