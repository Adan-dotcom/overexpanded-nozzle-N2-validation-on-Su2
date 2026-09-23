#!/bin/bash
# run_steady.sh CASE MESH NPR [NP] [ITER_A] [ITER_B]
#   Stage A: first-order, CFL 0.05 with CFL_ADAPT (as the old campaign's startup)
#   Stage B: MUSCL + Venkat-Wang, CFL_ADAPT up to 20
# Seed: reservoir fill (same as the unsteady Phase-1 case).
# Writes STATUS; at the end reports whether the density residual converged.
set -u
SRC=${SRC:-/mnt/d/eilnerCC}; SU2=${SU2:-/mnt/d/SU2/v8.5.0/bin/SU2_CFD}
# OpenMPI 5 removed the legacy "pt2pt" OSC component; use its default.
CASE=$1; MESH=$2; NPR=$3; NP=${4:-6}; ITER_A=${5:-500}; ITER_B=${6:-4000}
P_AMB=101325.0; T_AMB=300.0; T0=300.0
P0=$(python3 -c "print($NPR*$P_AMB)")
W=$HOME/su2-work/$CASE; mkdir -p $W; cd $W || exit 1
status() { echo "$(date -Is) $*" | tee -a STATUS; }
: > STATUS
cp $SRC/su2/meshes/$MESH . 2>/dev/null || cp $SRC/su2/$MESH . 2>/dev/null || { status "mesh $MESH not found"; exit 1; }
cp $SRC/su2/meshes/${MESH%.su2}_idmap.npz . 2>/dev/null
status "case=$CASE mesh=$MESH NPR=$NPR P0=$P0 np=$NP"
python3 $SRC/su2/make_seed.py $MESH seed.csv $P0 $T0 $P_AMB $T_AMB $SRC/dlr_par_real_geometry.lua >> STATUS || exit 1

cfg() { local out=$1; shift; cp $SRC/su2/steady_template.cfg "$out"
  for kv in "$@"; do sed -i "s|@${kv%%=*}@|${kv#*=}|g" "$out"; done
  sed -i "s|@P0@|$P0|; s|@T0@|$T0|; s|@P_AMB@|$P_AMB|; s|@T_AMB@|$T_AMB|; s|@MESH@|$MESH|" "$out"
  grep -q '@' "$out" && { status "unfilled placeholder in $out"; grep '@' "$out"; exit 2; }; }
run() { status "stage $1 start ($2 iters)"; local t0=$(date +%s)
  mpirun --allow-run-as-root -np $NP $SU2 $1.cfg > log_$1.txt 2>&1
  local rc=$?; local el=$(( $(date +%s) - t0 ))
  [ $rc -ne 0 ] && { status "stage $1 FAILED rc=$rc after ${el}s"; tail -20 log_$1.txt >> STATUS; exit 3; }
  status "stage $1 done in ${el}s"; }

cfg A.cfg STAGE=A RESTART_SOL=YES READ_BINARY=NO SOLUTION=seed RESTART=restart_A ITER=$ITER_A \
    CFL=0.05 CFL_ADAPT=YES CFL_MIN=0.01 CFL_MAX=2.0 MUSCL=NO VENKAT=0.05 WRT=$ITER_A
run A $ITER_A
cfg B.cfg STAGE=B RESTART_SOL=YES READ_BINARY=YES SOLUTION=restart_A RESTART=restart_B ITER=$ITER_B \
    CFL=1.0 CFL_ADAPT=YES CFL_MIN=0.05 CFL_MAX=20.0 MUSCL=YES VENKAT=0.001 WRT=500
run B $ITER_B
python3 - <<'PY' | tee -a STATUS
import csv, glob
h = sorted(glob.glob("history_B*.csv"))[-1]
rows = [r for r in csv.reader(open(h))][1:]
col = [i for i, c in enumerate(next(csv.reader(open(h)))) if "rms[Rho]" in c][0]
r0, r1 = float(rows[0][col]), float(rows[-1][col])
best = min(float(r[col]) for r in rows)
print(f"steady residual rms[Rho]: start {r0:.2f} -> end {r1:.2f} (best {best:.2f}), {len(rows)} iters")
print("VERDICT:", "CONVERGED" if r1 <= -6 else ("PARTIAL (stalled)" if r1 < -3 else "NOT CONVERGED"))
PY
status "ALL DONE"
