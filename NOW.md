# Current instructions — read this after every `git pull`

Updated: 2026-09-22, late evening. This file always holds the live state; the
README holds the stable procedure.

## Status

- **Lane B (L2 unsteady) is on hold.** Your run diverged at step ~936. It was not
  your fault and not a mesh problem: the same failure happened on the other
  machine on the L3 mesh. With `dt = 1e-7` and 30 inner iterations, the per-step
  residual drop collapses towards zero on the fine meshes and the run dies. The
  coarse meshes (L0, L1) were unaffected, which is why it was not caught earlier.
- **Your OpenMPI 5 fix was correct** and is now in the repo. Thanks — keep it.
- A settings matrix (dt, inner iterations, preconditioner) is running on the other
  machine right now to find the cheapest configuration that keeps the per-step
  drop healthy. The corrected lane-B command will be published here when it ends.

## What to do now

1. `git pull`
2. **Do not relaunch lane B (L2 unsteady) until this file says so.**
3. Retry task A (steady RANS) with a gentler ramp — it is independent of the
   problem above, and its answer decides the strategy for the whole dataset:

```bash
CFL_MAX_B=5 bash su2/run_steady.sh steadyL2_NPR50_soft mesh_L2.su2 50 6 2000 6000
```

That is: 2000 first-order iterations, then up to 6000 with the adaptive CFL
capped at 5 instead of 20.

4. Report, in `results/`, whether it **converges** (rms[Rho] <= -6), **stalls**
   (falls a few decades then flattens) or **diverges with NaN**, and at which
   iteration. A stall is a scientific result, not a failure: it is evidence the
   flow is genuinely unsteady. Do not force it with more iterations.

## Useful metric to report from now on

For any unsteady run, what matters is not the residual level but **how many
decades rms[Rho] drops within each physical step** (from inner iteration 0 to the
last one of that step). Healthy is >= 1.5-2 decades. If it falls below ~0.5 and
keeps sinking, the run is dying — stop it and report, do not wait for the NaN.
