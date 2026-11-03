# Current instructions — read this after every `git pull`

Updated: 2026-11-03, **third revision of the day. This one overrides the second.** If you already
pulled the revision that asked for five hot variants, that request is withdrawn — see section 1.

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
