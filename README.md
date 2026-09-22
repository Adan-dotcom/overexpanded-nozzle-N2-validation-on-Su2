# Handoff: steady-RANS lane (DLR-PAR nozzle, SU2) — for the second 6-core PC

You are running **one independent lane** of a larger CFD campaign. The other PC
runs the unsteady (URANS) lane; do not duplicate it. Everything you need is in
this folder. Read the whole file before running anything.

## 1. What this lane must answer

**Question 1 (gating, ~2 h): does steady RANS converge for this flow?**
Shock-induced separation in an overexpanded nozzle is physically unsteady.
A previous SU2 campaign on this geometry stalled at `rms[Rho] ~ 1e-2`, and an
Eilmer steady attempt died in its preconditioner. So this is a real open
question, not a formality. If steady converges, an NPR sweep becomes cheap
(hours instead of weeks) and gives both the paper's `x_sep(NPR)` curve and the
dataset for sensor placement (POD + QR).

**Question 2 (only if Q1 passes, ~1 day): the NPR sweep**
20–30 steady cases over NPR (and later wall temperature), all on mesh L2.

**Do not** run unsteady/URANS cases here, and do not change physics settings
(gas, turbulence model, boundary conditions). They were validated on the other
machine; keeping them identical is what makes the two lanes comparable.

## 0. Start here

Copy this whole folder to the second PC (any location; `D:\eilnerCC\handoff_steady`
keeps the examples below literal), then in WSL Ubuntu run:

```bash
bash /mnt/d/eilnerCC/handoff_steady/setup_and_verify.sh
```

It checks dependencies, finds SU2, verifies every file is present, and runs a
~1 minute end-to-end smoke test (60 iterations on a small mesh, physically
meaningless, but it proves the toolchain works). It **never calls sudo**: if
something is missing it prints the exact command for you to run. It ends by
printing the command for the real run. Do not start the 1-2 h run until it says
`SETUP OK`.

## 2. Environment (one-time, ~30 min)

Windows + WSL2 Ubuntu (22.04 or 24.04), 6 cores.

```bash
sudo apt update && sudo apt install -y openmpi-bin libopenmpi-dev python3-pip
pip3 install numpy scipy matplotlib
```

SU2 **v8.5.0** (must be this version; configs use v8 syntax):
- Easiest: copy the folder `D:\SU2\v8.5.0` from the other PC. The binary is a
  Linux ELF and runs under WSL directly.
- Or download the official Linux build from https://su2foundation.org and unpack it.

Check:
```bash
/mnt/d/SU2/v8.5.0/bin/SU2_CFD --help | head -2     # must print v8.5.0 "Harrier"
mpirun --version | head -1
```

If SU2 lives elsewhere, export `SU2=/path/to/SU2_CFD` before calling the scripts.

## 3. What this package contains

```
README.md                    # this file
setup_and_verify.sh          # run this first
dlr_par_real_geometry.lua    # the real 385-point contour (do not edit)
su2/steady_template.cfg      # steady config template
su2/run_steady.sh            # driver (stage A first order -> stage B MUSCL)
su2/make_seed.py             # initial condition writer
su2/check_su2_phase1.py      # checks (T by region, x_sep, wall pressure)
su2/meshes/mesh_L0.su2 + _idmap.npz   # 5.8k cells, smoke tests only
su2/meshes/mesh_L2.su2 + _idmap.npz   # 42k cells, THIS LANE'S MESH
```

The meshes are already converted to SU2 format, so **you do not need Eilmer** and
you do not need to generate any geometry. `*_idmap.npz` maps mesh nodes to
(block, i, j) and is required by the checks; keep each next to its mesh.

The only thing not included is SU2 itself (too large): copy the folder
`D:\SU2\v8.5.0` from the other PC, or download the official Linux build.

Paths: the scripts use `SRC` (this folder) and `SU2` (the binary). Both are
auto-detected by `setup_and_verify.sh`, which prints the exact command to use.

## 4. Run Q1: the convergence test

```bash
bash /mnt/d/eilnerCC/su2/run_steady.sh steadyL2_NPR50 mesh_L2.su2 50 6
```

Runtime ~1–2 h. It writes to `~/su2-work/steadyL2_NPR50/`, logs progress to
`STATUS`, and prints a verdict:

- `CONVERGED` — final `rms[Rho] <= -6`. Q1 passes; go to section 5.
- `PARTIAL (stalled)` — residual falls a few decades then flattens. **This is the
  expected outcome if the flow is genuinely unsteady.** Report it; do not try to
  force it with more iterations.
- `NOT CONVERGED` / crash — report it with the last 30 lines of `log_B.txt`.

Then run the checks (physical sanity, not just residuals):

```bash
python3 /mnt/d/eilnerCC/su2/check_su2_phase1.py ~/su2-work/steadyL2_NPR50 \
        /mnt/d/eilnerCC/results/steadyL2_NPR50 300 5066250 101325
```

The script detects a steady run (no `TIME_STEP` in the config), judges the final
state instead of a time window, and prints `dt=0`. The `iter`/`t` columns are then
meaningless; every other number (T by region, x_sep, wall pressure) is valid.
The plot it writes also overlays the unsteady lane's wall pressure when that file
is present, which it will not be on this PC — the overlay is simply skipped.

**Report back:** the verdict line, `x_sep` measured **from the throat**, the
residual history (`history_B*.csv`), and the summary text file.

## 5. Run Q2: the NPR sweep (only after Q1 passes and the other lane confirms)

```bash
for NPR in 20 25 30 35 40 45 50 60 70 80 100 120 150; do
  bash /mnt/d/eilnerCC/su2/run_steady.sh steadyL2_NPR$NPR mesh_L2.su2 $NPR 6
done
```

Each case is independent. Report, per NPR: verdict, `x_sep` from the throat, and
the wall-pressure file. Do not average or interpret across cases; the other lane
does the comparison.

## 6. Physics reference (do not change without being asked)

| Item | Value |
|---|---|
| Gas | N2 ideal, gamma 1.4, R 296.8, Sutherland (1.663e-5, 273 K, 107 K) |
| Turbulence | SST V2003m (no Sarkar correction) |
| Stagnation | T0 = 300 K, P0 = NPR x 101325 Pa |
| Ambient | 101325 Pa, 300 K |
| Wall | adiabatic no-slip (config A) |
| Geometry | throat at x = 22.680 mm, r = 10 mm; exit x = 147.70 mm, r = 54.77 mm |
| Numerics | SLAU2, MUSCL + Venkatakrishnan-Wang 0.001, implicit Euler, FGMRES+ILU0 |

**Always report `x_sep` measured from the throat** (subtract 22.680 mm), which is
the convention the reference tables use.

## 7. Pitfalls already paid for — do not rediscover them

- **`HISTORY_WRT_FREQ_INNER= 0` crashes SU2** with an integer divide-by-zero.
  Never set any output frequency to 0.
- **The initial condition matters.** The seed fills the converging section with
  reservoir gas and leaves the rest ambient. An abrupt start (imposing the
  supersonic solution against ambient) blew up the previous campaign.
- **SU2 restart CSV naming**: unsteady restarts need the `_00000` suffix;
  steady ones do not. `run_steady.sh` handles this.
- **With SST, `Energy` in the restart file includes k**:
  `T = (gamma-1)/R * (E/rho - |u|^2/2 - k)` (verified in `CNSVariable.cpp:145`).
  Getting this wrong shifts temperatures by several K.
- **T > T0 outside the nozzle is usually not a bug.** Ambient air compressed by
  the jet legitimately exceeds 300 K, because the ambient starts at T0 by
  coincidence. It disappears when the ambient is set to 250 K. Judge the
  criterion **inside the nozzle**, and report the external value separately.
- **Known open item**: a total-temperature excess of a few percent in the first
  cell rows next to the axis, in the plume, outside the nozzle. It appears in
  two different solvers. Record it; don't chase it.
- **Disk**: keep the WSL disk on D:, not C:. Moving it:
  `wsl --shutdown` then `wsl --manage Ubuntu --move D:\WSL\Ubuntu`.
- **Do not run 6 MPI ranks while another heavy job runs**; it distorts timings
  and can exhaust RAM.

## 8a. Returning results through this repo

This repo is the channel in both directions. To publish a finished run:

```bash
bash /path/to/repo/collect_results.sh steadyL2_NPR50      # copies the small files into results/
cd /path/to/repo
git add -A results && git commit -m "steady L2 NPR50: <verdict in a few words>" && git push
```

`collect_results.sh` copies only `STATUS`, the history CSV, the final wall CSV,
the configs and the check summary (a few hundred kB). **Never commit restart,
`flow_*`, or volume files**; `.gitignore` blocks them, do not force them in.

Before starting work, and after finishing, run `git pull` — the other lane may
have left you updated instructions in this README.

If a push is rejected because the history moved, `git pull --rebase` then push.
Never force-push this repo.

## 8. What to send back

For each run: the `STATUS` file, `history_B*.csv`, the check summary, and the
`wall_B*.csv` of the final iteration. These are small. Do not ship restart or
volume files unless asked.

Report honestly if a case stalls or crashes: a stalled steady run is a
**scientific result** here (evidence the flow is unsteady), not a failure to hide.
