# Current instructions — read this after every `git pull`

Updated: 2026-11-03, second revision of the day. **The diagnosis has moved. Read section 2
before running anything** — the task has changed and the variant priority with it.

## 1. Your `inner60` landed, and it answered more than it was asked

`results/hot_matrix/inner60`, pushed 2026-11-03 11:23. Only that one variant arrived, so the
other four are presumably still queued or were never started. Here is what it says.

The config is verified correct: LUT v4 loaded ("LUT fluid model ready for use", 23562 triangles),
Roe, SST-2003m, 60 inner iterations, dt 2e-8, first order in space and time, mesh L2, and all six
markers assigned as intended (INLET/OUTLET/FARFIELD Riemann, WALL heat flux, AXIS symmetry,
SHROUD Euler). No out-of-range or NaN warnings anywhere in the log. The measurement is sound.

It diverged at physical step **334** (`Residual > 10^20`), against ~303 for the 30-inner case.

| | inner 30 | inner 60 |
|---|---|---|
| step at divergence | ~303 | 334 |
| median decades per step | 0.296 | **0.286** |

**Doubling the inner iterations changed the per-step convergence by 0.01 decades.** It is not
iteration count. That candidate is eliminated — a real result, and the first one the matrix has
produced.

The run was also never healthy, which the step count hides: of its 334 steps only **41 met the
>= 1.2 criterion**, and **49 had a negative drop** — the inner loop diverging within the step.
Steps 2 and 4 reached 1.5 and 1.9 decades and it decayed to ~0.25 by step 75 and stayed there.
"It reached step 300" was never convergence.

## 2. The find: the turbulence equations go first, by 150 steps

First step at which each residual exceeds its own step-50 value by 2 decades:

| residual | crosses +2 decades at step |
|---|---|
| **rms[k]** | **121** |
| rms[w] | 159 |
| rms[Rho] | 239 |
| rms[RhoV] | 272 |
| rms[RhoE] | 277 |
| rms[RhoU] | 278 |

`rms[k]` destabilises at step 121 and climbs 4 decades over the next 20 steps while `rms[Rho]`
and `rms[RhoU]` sit flat. The flow follows 150 steps later. Total growth over the run:
rms[k] **+13.47 decades**, rms[Rho] +6.14.

Against the validated cold runs in this same repository:

| case | steps | rms[k] grew |
|---|---|---|
| cold L2 N2 NPR 50 | 933 | +1.96 dec |
| cold L3 N2 NPR 50 | 19701 | +0.97 dec |
| cold L3 NPR 33 | 29997 | **+0.10 dec** |
| **hot inner60** | **334** | **+13.47 dec** |

In every cold run `rms[k]` grew *less* than `rms[Rho]`. In the hot run it grew more than twice
as much. This behaviour has no counterpart anywhere in the cold campaign.

### The mechanism, read out of the SU2 source

`CEulerSolver.cpp:1070` and `:1076`:

    Tke_FreeStream   = 1.5 * ModVel^2 * I^2
    Omega_FreeStream = rho * k / (mu * TURB2LAMVISCRATIO)

Both are proportional to the **freestream velocity**, and our freestream is a quiescent ambient:
`MACH_NUMBER= 0.001` with a = 486 m/s gives ModVel = 0.486 m/s. SU2 therefore reports, and
initialises **every point of the field** with (`CTurbSSTSolver.cpp:152`):

    k_inf     = 3.5457e-05 m^2/s^2
    omega_inf = 0.201254 1/s      ->  1/omega = 5 seconds

The whole run spans 900 * 2e-8 = 1.8e-5 s. Omega cannot relax; it is effectively frozen at its
initial value. And the eddy-viscosity limiter (`CTurbSSTSolver.cpp:249`) is

    muT = rho * a1 * k / max(a1*omega, S*F2)        a1 = 0.31

Wherever the strain rate is low, the denominator falls back on `a1*omega = 0.062`, giving
**muT = 5*rho*k**. The hot plume's shear layer generates k of order (0.1*U_e)^2 with U_e ~ 4000
m/s, i.e. ~1e5 m^2/s^2, so in any adjacent low-strain pocket muT reaches ~1e5 Pa.s — about
**1e10 times the molecular viscosity**.

Why the cold case survived the same formula: omega_inf is nearly identical there (~0.12 1/s), but
U_e is ~700 m/s, so the k being produced is ~30x smaller, and the sound speed is 4.5x lower.
Same latent weakness, pushed roughly two orders of magnitude harder.

**This is the leading hypothesis, not a proven cause.** The alternative is that the flow is
already wrong in a way `rms[Rho]` does not yet show and `k` is merely the most sensitive
reporter. The test below separates the two.

## 3. Script fixes — `git pull` before you run anything

**The `n2cold` control was broken by a real bug and now works.** The common block rewrote
`MARKER_RIEMANN` *after* the n2cold branch had set it, so the cold-N2 control was being run with
a total temperature of **3265.5 K** and the burnt mixture's Sutherland constants
(mu_ref 1.0086e-5, S = 773 instead of 1.716e-5 and S = 111). It was never a control at all. Fixed
by making T0, mu_ref, S and Pr per-variant and writing the marker once.

Verified locally before this push, which is what was missing last time: the generated configs
were inspected field by field, and every variant below was run for 8 real steps under SU2.
**`n2cold` now runs at 5.80 decades per step** — the matrix has a working known-good case for the
first time. The previous note telling you the ideal-gas branch was broken and to skip it is
withdrawn for `n2cold`; `ideal` is still unexplained and is left out of the loop.

Three variants are new:

| variant | what it changes | what it tells us |
|---|---|---|
| `laminar` | `SOLVER= NAVIER_STOKES`, no turbulence model | **decisive.** Survives past 334 -> SST is the cause |
| `sa` | Spalart-Allmaras: one equation, no omega | if SA holds and SST does not, confirms, and gives a way forward |
| `omegahi` | `TURB2LAMVISCRATIO` 10 -> 1e-4, i.e. omega_inf x 1e5 | attacks the mechanism directly: drops the muT ceiling by 1e5 |

## 4. Task: split with the laptop, do not duplicate

The laptop is already running `laminar`, `n2cold` and `omegahi` at 420 steps each. **Do not run
those three.** Yours:

```bash
git pull
for v in base sa dt1e-8 dt5e-9 muscl; do bash hot/hot_matrix.sh $v; done
```

900 steps each, about 2.5 hours in all; two at a time if you have the cores.

| variant | what it changes | candidate |
|---|---|---|
| `base` | the reference (LUT, dt 2e-8, first order, SST) | the baseline the rest compare against |
| `sa` | Spalart-Allmaras instead of SST | the turbulence hypothesis |
| `dt1e-8` | dt halved | dt too large for the hot acoustics |
| `dt5e-9` | dt quartered | same |
| `muscl` | second order with Venkat 0.001 | first order plus table interpolation |

**Report for each**: exit code, whether `has diverged` appears, the step it reached, and the
median and minimum decades per step over the last 200 steps. The script prints all of it and
appends to `RESUMEN`. Push `log.txt`, `history_*.csv` and `RESUMEN` per variant — and please push
the whole work root this time, not one subdirectory, so the `RESUMEN` arrives complete.

`inner60` is done; do not repeat it.

## 5. Then, without waiting: the long cold spectral record

Unchanged and still the other IAC deliverable. Start the **20 ms L3 cold record at NPR 33**,
continuing from your existing 10 ms solution; 20 ms brings the resolution to ~50 Hz, which is
what it takes to resolve the measured 300 and 800 Hz peaks instead of reporting a red spectrum
with no peak. Roughly two weeks. Kill it without hesitation when the hot production run is ready
— the partial record stays usable, the segments being physically continuous.

## 6. Standing rules

- Health metric: decades of residual drop **within** each physical step (>= 1.2), over hundreds
  of steps, never tens. `python3 su2/decades.py history_*.csv`
- **Watch `rms[k]` and `rms[w]`, not only `rms[Rho]`.** That is the lesson of this result: the
  density residual was flat and healthy-looking for 118 steps after the run had already lost the
  turbulence equations.
- **Absence of an error message is not proof of success.** Three "passes" in this campaign were
  false: a boundary probe where SU2 was not starting, a hot smoke test whose checker had the
  table bounds hardcoded wrong, and a 200-step hot run that "looked healthy" and died at 303.
  Always require a positive signal.
- dt per mesh, cold: L2 -> 1e-7, L3 -> 5e-8.
- With a non-ideal fluid SU2 rejects `MARKER_OUTLET` **and** `MARKER_FAR` (CConfig.cpp:4299 and
  4304 — the far-field check prints the outlet error text, a copy-paste bug in SU2 and very
  misleading). Both must be `MARKER_RIEMANN`.
- Restarts every 2500 steps. AC power, sleep disabled.
- Do not change physics settings outside the variant being tested.

## 7. The other machines

- **Laptop**: running `laminar`, `n2cold`, `omegahi` at 420 steps. Script validated here against
  real SU2 before this push, not only by inspection.
- **Cloud**: deleted, and the API token and server credentials have now been wiped locally.
