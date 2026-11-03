# Current instructions — read this after every `git pull`

Updated: 2026-11-03. **The NPR 40 task is cancelled. We are moving to hot gas.**

## 1. NPR 40 on the fine mesh: received, and it matters more than expected

Your result landed (`results/p10_L3_NPR40`, finished 2026-10-11). It was missed on this end for
three weeks — checked with a `git fetch --dry-run` whose output was truncated instead of a real
fetch. That is on us, not on you.

    x_sep = 82.80 mm, rms 0.199 mm, drift -0.03 mm/ms, settled over 2.5-5.0 ms
    DLR    = 101.66 mm  ->  -18.55 %

Put next to NPR 33 it is the most useful thing in the campaign right now:

| NPR | medium mesh | fine mesh |
|---|---|---|
| 33 | -17.7 % | **-1.1 %** |
| 40 | -25.9 % | **-18.55 %** |

The fine mesh **completely fixes NPR 33 and does not fix NPR 40**. So the accuracy loss near the
RSS transition is not a discretisation artifact — it is the model. That turns a poster conclusion
that rested on medium-mesh inference into a result with fine-mesh evidence, and it bounds the
axisymmetric model's domain of validity cleanly. Nothing further is needed on NPR 40.

## 2. What happened since your last push

The thermochemistry was audited against real NASA CEA output (LOX/LH2, O/F 6.0, 1000 psia,
equilibrium). The chemistry is solid:

| against NASA CEA | difference |
|---|---|
| flame temperature (computed from propellant enthalpies, not imposed) | +0.14 % |
| molar mass | +0.05 % |
| equilibrium isentropic gamma | −0.01 % |
| equilibrium sound speed | +0.04 % |
| c* | +0.04 % |

Two corrections to the record came out of it. **The gamma of 1.19 in the old notes was the
frozen one**; CEA reports the equilibrium isentropic exponent, 1.1401, and that is what the
table carries and what we cite from now on. And the c* that was logged as "2–5 % low against
published" was not a model deficiency — it was frozen gamma used in a formula that wants the
equilibrium one. With the right convention it is +0.04 %.

The table was regenerated (**`hot/LOXLH2_eq_v4.drg`**, 12000 points). The previous one excluded
the ambient state and the plume core from its domain, which is why everything downstream of it
misbehaved. v4 covers rho 0.002–6.912 and e −1.3230e7 to −2.0029e6, matches Cantera to 0.0001 %
at interior points, and its gamma matches CEA at the chamber to +0.22 %.

## 3. The problem you are being asked to solve

**The hot case diverges.** At NPR 10, from a cold start, it dies around physical step 303 with
`SU2 has diverged (Residual > 10^20)`. A 200-step run looked healthy — it was not; that was a
short-record illusion, the same trap the poster is about. Only a very mild case (3 bar, 1000 K)
converges well, at 4.34 decades per step.

There are four candidates and nobody has distinguished them:

1. dt = 2e-8 still too large for the hot acoustics on L2 (a = 1567 m/s against 350 cold)
2. first order combined with the table interpolation
3. `TOTAL_CONDITIONS_PT` at the inlet with a non-ideal fluid (SU2's SLAU2 jacobian already
   turned out to assume ideal gas; the total-to-static conversion could have the same vice)
4. the density jump at the nozzle/ambient interface

## 4. Task: the diagnostic matrix

```bash
git pull
bash hot/hot_matrix.sh todas          # 6 variants, 900 steps each at NPR 10
```

Six variants, one thing changed at a time, exactly like `inner_matrix_L3` did for the cold
case — the methodology that worked:

| variant | what it changes | what it tells us |
|---|---|---|
| `ideal` | ideal gas, gamma 1.1401, R 617.1 | **the decisive one**: if this runs and `base` does not, the problem is the TABLE |
| `base` | the reference (LUT, dt 2e-8, first order) | the baseline to compare against |
| `dt1e-8` | dt halved | candidate 1 |
| `dt5e-9` | dt quartered | candidate 1 |
| `muscl` | second order with Venkat 0.001 | candidate 2 |
| `inner60` | 60 inner iterations instead of 30 | whether it is just iteration count |

Each run is 900 steps, which is **three times longer than where the divergence appeared**, so a
variant that survives to the end has actually earned it.

**Report for each variant**: exit code, whether `has diverged` appears in the log, and the
median/min decades of residual drop per physical step over the last 200 steps. The script prints
all of it and leaves a `RESUMEN` file. Push `log.txt`, the `history_*.csv` and `RESUMEN` for each.

If the tower has cores for two jobs at once, run them two at a time; the variants are
independent. Sequentially it is about 3 hours in total.

## 5. Then, without waiting for me: the long cold spectral record

The hot production run cannot start until the diagnosis above is read, so do not leave the
machine idle. Start the **20 ms L3 cold record at NPR 33**, continuing from your existing 10 ms
solution. It is the other IAC deliverable and it is completely independent of the hot work: with
20 ms the resolution reaches ~50 Hz, which is what it would take to actually resolve the measured
300 and 800 Hz peaks instead of reporting a red spectrum with no peak.

It is roughly two weeks of your machine. Kill it without hesitation when the hot production run
is ready — the partial record is still usable, since the segments are physically continuous.

## 6. Standing rules

- Health metric: decades of residual drop **within** each physical step (>= 1.2), measured over
  hundreds of steps, never tens. `python3 su2/decades.py history_*.csv`
- **Absence of an error message is not proof of success.** Two "passes" in this campaign were
  false: a boundary probe where SU2 was not even starting, and a hot smoke test whose checker had
  the table bounds hardcoded wrong. Always require a positive signal.
- dt per mesh, cold: L2 -> 1e-7, L3 -> 5e-8. For hot, that is exactly what the matrix is measuring.
- With a non-ideal fluid SU2 rejects `MARKER_OUTLET` **and** `MARKER_FAR` (CConfig.cpp:4299 and
  4304 — the far-field check prints the outlet error text, which is a copy-paste bug in SU2 and
  very misleading). Both must be `MARKER_RIEMANN`.
- Restarts every 2500 steps. AC power, sleep disabled.
- Do not change physics settings outside the variant being tested.

## 7. The other machines

- **Laptop**: ran the audit. `hot/hot_ramp.sh` was run here and its config generation is
  verified. **`hot/hot_matrix.sh` is still being validated locally as this is pushed** — it is
  the same config-generation code, but if the local run turns up a problem a fix will land
  before you get to it, so `git pull` once more right before you start. If a variant fails with
  `PLANTILLA INCOMPLETA` or an empty cfg, stop and say so rather than working around it.
- **Cloud**: deleted.
