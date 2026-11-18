# Current instructions — read this after every `git pull`

Updated: 2026-11-17 (night). **Section 0 is the only thing that matters right now.** Section 0b is
the 16 November revision: its steps 1-3 are done (thank you, commit f4ad1e6); its step 4 (L22/L33)
is POSTPONED by section 0.

## 0. L3 at NPR 33 is not settled and is turning RSS. Extend it until it settles, not by 10 ms blocks.

What your push showed. Over the 10 ms extension x_p50 went from 74.7 to ~89.5 mm and was
**accelerating** at the end (~9 mm/ms over the last ms). The tau_w audit at step 192500 is **RSS**:
separation 83.4 mm, reattachment 123.4 mm, 1.6 mm before the exit. So the "settled" 74.81 mm at
10 ms was a pause, not a settled state. The DLR data at NPR 33 has two branches: startup (FSS)
75.7 mm and shutdown (RSS) 103.3 mm. Our history is one of decreasing NPR, i.e. shutdown-like.
**Where L3 ends up is now the question the paper hangs on**, more than the wall study.

### Step 1 — let the current run finish (200 000 steps), then push as before

```bash
RUN=/root/su2-work/<the p11 run dir>
python3 su2/wall_series.py $RUN 5.0e-8 results/spec20_L3_NPR33/serie_full.csv
python3 su2/topology.py $RUN x results/spec20_L3_NPR33/tau_w_final.csv | tee results/spec20_L3_NPR33/topology_final.txt
cp $RUN/STATUS $RUN/history_B_resume_*.csv $RUN/log_B_resume_*.txt results/spec20_L3_NPR33/
git add results/spec20_L3_NPR33 && git commit -m "Full 20 ms L3 record at NPR 33" && git push
```

### Step 2 — start the extension (new script, `su2/extend.sh`)

```bash
git pull
bash su2/extend.sh $RUN            # $RUN = the same p11 run dir; it seeds from its newest restart BY DATE
```

What it does, so you can tell if something is off:
- copies the newest `restart_*.csv` of `$RUN` (should be `restart_200000.csv`) as the seed, same
  mesh, no interpolation, and prints the seed's topology in STATUS (expect RSS);
- **probes the time step**: 300 steps at 1e-7 first, then 5e-8; keeps the first whose WORST step
  drops >= 1.2 decades. Larger steps are not tried: the 22 Sep L3 test failed at 2.5e-7. If none
  passes it stops with exit 4: report it, do not force it;
- runs in chunks of 2500 steps. After each chunk it checks the per-step decades, runs the tau_w
  audit on the new restart, rebuilds `serie.csv`, and writes one line to STATUS;
- **stops by itself** when settled: at least 2 ms, drift < 0.5 mm/ms in EACH of the last two 1 ms
  windows, and the same topology on every restart of the last 1 ms. Otherwise it stops at 10 ms
  and says NOT SETTLED.
- derived files go to `results/ext_L3_NPR33/` after every chunk: **push that folder once a day**
  (`git add results/ext_L3_NPR33 && git commit -m "L3 extension partial" && git push`), and at the end.
- cut off? `RESUME=1 bash su2/extend.sh $RUN` (picks the newest complete checkpoint pair by date).

Cost: L3 does ~1260 steps/h. At 1e-7 that is ~8 h per ms (2 days for 6 ms); at 5e-8, double.
Tested on the laptop 17 Nov on L1 (probe, chunks, stop at T_MAX, resume, stop at SETTLED).

### Postponed: L22 / L33 (section 0b, step 4)

Do not start them until the extension has finished and been pushed.

## 0b. (16 Nov) The 20 ms record was cut off with ~34 h left. Push what exists, then resume.

As of 14 November, `origin/main` is still at `2e58690`, the 3 November commit from the laptop.
**Nothing from the 20 ms record has arrived.** It exists on this machine and only here. Section 1
asked for partials every ~2500 steps and none came, so the push step is what broke. Most likely
cause: the raw `wall_*.csv` files are far too many for the repo (one every 50 steps over ~360k
steps on L3). **Push derived files, not raw ones.**

### Step 1 — push the partial, today, before anything else

```bash
cd /path/to/handoff_steady && git pull --rebase       # read this file first
RUN=/root/su2-work/<the 20 ms run dir>
mkdir -p results/spec20_L3_NPR33
python3 su2/wall_series.py $RUN 5.0e-8 results/spec20_L3_NPR33/serie_partial.csv
cp $RUN/history_*.csv $RUN/STATUS $RUN/log_*.txt $RUN/*.cfg results/spec20_L3_NPR33/
git add results/spec20_L3_NPR33 && git commit -m "Partial 20 ms L3 record at NPR 33" && git push
```

Do **not** add the raw `wall_*.csv` files or the restarts to git. The series has wall pressure at
13 stations every 50 steps, which is everything the spectral analysis needs.

In the commit message or in `results/spec20_L3_NPR33/README`, report: **the last physical step
reached, the time step, and the last complete restart pair.**

### Step 2 — resume it to the end

Resume from the most recent **consecutive** restart pair (BDF2 needs steps N-1 and N). Pick the
pair by **modification date, not by step number**: a run directory can hold restarts from an
earlier stage with higher step numbers, and resuming from one of those silently throws away the
work and corrupts the clock. This nearly happened on the laptop on 14 November.

When it finishes, run `wall_series.py` again on the full run and push `serie_full.csv` the same
way.

### Step 3 — topology audit of L3 (one minute, do it as soon as you read this)

```bash
python3 su2/topology.py $RUN x results/spec20_L3_NPR33/tau_w_L3.csv | tee results/spec20_L3_NPR33/topology_L3.txt
git add results/spec20_L3_NPR33 && git commit -m "Topology audit of L3 at NPR 33" && git push
```

It only reads the newest `restart_*.csv`, so it is safe while SU2 is running. It prints where the
wall shear stress changes sign and a verdict: FSS (reverse flow reaches the exit) or RSS
(reattachment inside the nozzle). **This one line decides how the rest is read**, see below.

### Step 4 — after the 20 ms record: the wall-resolution study

What happened on the laptop (16 November). L1 at NPR 33 finished and settled at **54.74 mm**.
With L2 = 62.25 and L3 = 74.81 the jumps are 7.5 and 12.6 mm: they **grow** with refinement, the
apparent order is negative, and Richardson/GCI do not apply at NPR 33. Two facts point at the wall:

- measured y+ is ~20 on L1, ~9.7 on L2 and 1.3-2.6 on L3. Only L3 is wall-resolved for SST;
- the audit shows **L1 (settled) and L2 (2.5 ms, unsettled) compute a closed bubble, RSS**,
  with reattachment at 107-110 mm, where the experiment at NPR 33 is FSS. L3 is unknown until
  step 3 runs.

So the three meshes may not be three resolutions of one flow. Two new meshes test it. Both are in
`su2/meshes/` and were generated from `su2/grid_template.lua` (levels 22 and 33):

| mesh | streamwise | wall-normal, first cell | cells | question |
|---|---|---|---|---|
| L22 | as L2 | as L3, 1.9 um | 55 050 | does resolving the wall alone move L2 from 62 to ~75 mm? |
| L33 | as L3 | 4.4x finer than L3, 0.43 um | 120 000 | does L3 stay at ~74.8 mm with a much finer wall? |

Run them in this order, one at a time:

```bash
bash su2/wallres.sh L22                                   # seed is in the repo; 10 ms
bash su2/wallres.sh L33 $RUN/restart_NNNNN.csv            # NNNNN = LAST restart of the 20 ms record; 5 ms
```

- The script **probes the time step itself** (300 steps per candidate, largest first) and keeps
  the first one whose worst step drops >= 1.2 decades. If none passes it stops with exit 4:
  **report that, do not force a smaller CFL or more inner iterations on your own.**
- L33 must be seeded from the **settled** L3 state, i.e. the last restart of the 20 ms record.
  Use the `.csv` restart, not the `.dat`.
- If it is cut off: `RESUME=1 bash su2/wallres.sh L22` (it picks the restart pair by date).
- When each finishes it writes derived files to `results/w_L22_NPR33` / `results/w_L33_NPR33`
  (series, trajectory, topology, y+, history). Push those. Never the raw `wall_*.csv` or restarts.
- Laptop probe, 16 Nov: both meshes fail or are untested at 1e-7 (L22: 0.10 decades) and pass at
  **5e-8** (worst step 1.58 on L22, 1.88 on L33). Expect ~4 days each. **Push the STATUS after the
  probe** so the laptop can confirm the time step your machine chose.

The history test from below and the settled SA run are moving to the laptop; they are no longer
yours.

## 1. Do NOT kill the cold spectral record. It is now the priority.

The previous revision told you to run five hot variants. **Ignore that.** It would have made you
abandon a two-week run for work that has since been done on the laptop, and it was a mistake on
this end.

If you are running the **20 ms L3 cold record at NPR 33**, keep running it. Reason: the EASN
full paper is due **15 December 2026** and it is the *cold* case. Twenty milliseconds brings the
spectral resolution to ~50 Hz, which is what it takes to resolve the measured 300 and 800 Hz
peaks instead of reporting a red spectrum with no peak, which is what the poster had to do. At
roughly two weeks it lands around 17 November, a month before the deadline. It is the single
most valuable thing your machine can be doing.

**One change to how you run it: push partial records as you go**, every ~2500 steps along with
the restarts, rather than only at the end. The segments are physically continuous, so a partial
record is usable, and it unblocks the paper's spectral section before the full 20 ms lands.

```bash
git pull            # read this file, then go back to what you were doing
# keep the cold record running; push partials periodically
```

## 2. Retraction: the turbulence hypothesis was wrong

The previous revision argued at length that the SST equations were leading the hot divergence,
on the evidence that `rms[k]` destabilises 150 steps before the flow residuals. That evidence was
real and is still in the record, but the conclusion was wrong.

`laminar` — identical case, `SOLVER= NAVIER_STOKES`, **no turbulence model at all** — diverged at
step **324**. Removing SST entirely changed nothing. `rms[k]` was simply the most sensitive
reporter, which was the alternative explicitly flagged as untested. Withdrawn.

## 3. What the control proved, which is the useful part

| variant | step reached | median decades/step | diverged |
|---|---|---|---|
| base (inner 30) | ~303 | 0.296 | yes |
| laminar (no turbulence model) | 324 | 0.201 | yes |
| inner 60 | 334 | 0.286 | yes |
| **n2cold (control, cold ideal N2)** | **420, full run** | **5.198** | **no** |

`n2cold` is the same mesh, the same dt, the same NPR, the same markers and the same numerics.
The only difference is the gas. It ran the whole record at 5.198 decades per step.

**So the mesh, the time step, the boundary setup, the NPR and the script are all fine. The
problem is the hot gas and nothing else.** That is the first time the matrix has been able to say
that, and it is only possible because the control was fixed.

## 4. The cause, isolated

The `ideal` variant (hot gas properties as an ideal gas, no table) still failed after the n2cold
fix, so its failure is a different one. Isolated on the laptop by changing one field at a time,
everything else held fixed, 8 steps each:

| change | result |
|---|---|
| untouched, inlet T0 = 3265.5 K | **NaN on step 1** |
| **inlet T0 = 300 K** | **runs** |
| gamma 1.1401 -> 1.4 | NaN |
| R 617.1 -> 296.8 | NaN |
| Sutherland constants of N2 | NaN |
| inlet T0 = 1500 K | NaN |

**It is the total temperature at the `TOTAL_CONDITIONS_PT` inlet.** Not gamma, not the gas
constant, not the viscosity, not the table. Imposing a hot total temperature against a field
initialised at 300 K is what breaks it — instantly with an ideal gas, at step ~303 through the
table.

This accounts for everything at once: why base, laminar and inner60 all die between 303 and 334
regardless of turbulence model or iteration count; why `n2cold` survives, its T0 being 300 K;
and why neither halving dt nor doubling the inner iterations moved the result.

It also exposes something that had been missed: **`hot_ramp.sh` ramps the pressure but never the
temperature.** T0 is 3265.5 K from step 1 in every stage. The temperature jump was never ramped
and was never initialised away.

## 5. The fix being tried on the laptop — not your job yet

Not a temperature ramp. A ramp spends real simulated time and leaves a spurious transient in the
record. Instead, **initialise the field with the hot gas already in the chamber**: instantaneous,
costs no simulated time, and has no physical interpretation to defend.

With one constraint that is not optional. This nozzle is bistable: FSS and RSS coexist over a
range of NPR, and which branch you land on depends on history. From the DLR data, at NPR 30 the
startup branch gives x_sep = 61.55 mm and the shutdown branch 93.58 mm — same NPR, different
answer. So the initial field has to be consistent with an *increasing*-NPR history, because that
is the branch the measurements we validate against were taken on. "Initialise it hot somehow" is
not safe.

This will be developed and tested on the laptop first. You will get it as a working script.

## 6. Hot variants: only if the machine would otherwise be idle

The five variants from the previous revision are no longer the main line. If and only if the cold
record finishes or you have spare cores, these three are still worth having as confirmation,
in this order:

```bash
for v in base muscl dt1e-8; do bash hot/hot_matrix.sh $v; done
```

| variant | what it changes | what it still adds |
|---|---|---|
| `base` | the reference | a clean in-matrix baseline; only the ramp's ~303 exists today |
| `muscl` | second order, Venkat 0.001 | whether first order plus table interpolation contributes |
| `dt1e-8` | dt halved | bounds how much dt contributes on top of the inlet defect |

`inner60` is done, do not repeat it. `sa` and `omegahi` are moot now that `laminar` diverged.
`laminar` and `n2cold` were run on the laptop.

**A script bug that affected your last push:** `hot_matrix.sh` truncated `RESUMEN` on every
invocation, so running one variant at a time wiped the previous lines and `RESUMEN` arrived with a
single entry. Fixed — it now only truncates when called with `todas`. If you did run more than
`inner60`, their logs are still in your work root and are worth pushing.

## 7. Standing rules

- Health metric: decades of residual drop **within** each physical step (>= 1.2), over hundreds
  of steps, never tens. `python3 su2/decades.py history_*.csv`
- **Watch `rms[k]` and `rms[w]` as well as `rms[Rho]`** — not because turbulence is the cause, it
  is not, but because they move first and buy ~150 steps of warning.
- **Absence of an error message is not proof of success.** Four "passes" in this campaign were
  false: a boundary probe where SU2 was not starting, a hot smoke test whose checker had the table
  bounds hardcoded wrong, a 200-step hot run that looked healthy and died at 303, and a control
  variant that was never testing what it claimed. Always require a positive signal.
- Equally: **a hypothesis with good evidence is still a hypothesis.** The turbulence story in the
  previous revision had a 150-step lead time behind it and was still wrong. Test it before acting.
- dt per mesh, cold: L2 -> 1e-7, L3 -> 5e-8.
- With a non-ideal fluid SU2 rejects `MARKER_OUTLET` **and** `MARKER_FAR` (CConfig.cpp:4299 and
  4304 — the far-field check prints the outlet error text, a copy-paste bug in SU2 and very
  misleading). Both must be `MARKER_RIEMANN`.
- Restarts every 2500 steps. AC power, sleep disabled.
- Do not change physics settings outside the variant being tested.

## 8. The other machines

- **Laptop**: finishing `omegahi`; then the hot initial-field work of section 5, and the EASN
  paper. `laminar` and `n2cold` ran here. Script changes are validated against real SU2 here
  before they are pushed to you.
- **Cloud**: deleted; API token and server credentials wiped.
