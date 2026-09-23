#!/bin/bash
# run_from_seed.sh CASE MESH SEED.csv[.gz] N_STEPS [NP]
# Unsteady (URANS) continuation from an already-developed solution:
#   stage A: 3 BDF1 steps (first order) to create the two time levels BDF2 needs
#   stage B: BDF2 + MUSCL, dt from $DT (default 1e-7), pseudo-CFL from $CFLB (default 2), 30 inner.
# The seed must be an SU2 restart CSV on the SAME mesh (see README lane B).
set -u
SRC=${SRC:-/mnt/d/eilnerCC}; SU2=${SU2:-/mnt/d/SU2/v8.5.0/bin/SU2_CFD}
CASE=$1; MESH=$2; SEED=$3; NSTEP=$4; NP=${5:-6}
CFLB=${CFLB:-2.0}; NA=${NA:-3}   # env: stage-B pseudo-CFL, number of first-order start-up steps
DT=${DT:-1.0e-7}; P0=5066250.0; T0=300.0
case "$SEED" in /*) ;; *) SEED="$SRC/$SEED" ;; esac
W=$HOME/su2-work/$CASE; mkdir -p $W; cd $W || exit 1
status() { echo "$(date -Is) $*" | tee -a STATUS; }
: > STATUS
cp $SRC/su2/meshes/$MESH . || { status "mesh $MESH not found"; exit 1; }
cp $SRC/su2/meshes/${MESH%.su2}_idmap.npz . 2>/dev/null
case "$SEED" in
  *.gz) zcat "$SEED" > seed_00000.csv || { status "cannot read seed $SEED"; exit 1; } ;;
  *)    cp "$SEED" seed_00000.csv      || { status "cannot read seed $SEED"; exit 1; } ;;
esac
status "case=$CASE mesh=$MESH seed=$(basename $SEED) steps=$NSTEP np=$NP dt=$DT cflB=$CFLB startup=$NA"

cfg() { local out=$1; shift; cp $SRC/su2/phase1_template.cfg "$out"
  for kv in "$@"; do sed -i "s|@${kv%%=*}@|${kv#*=}|g" "$out"; done
  sed -i "s|@T_AMB@|300.0|; s|@P0@|$P0|; s|@T0@|$T0|; s|@DT@|$DT|; s|@MESH@|$MESH|" "$out"
  grep -q '@' "$out" && { status "unfilled placeholder in $out"; exit 2; }; }
run() { status "stage $1 start"; local t0=$(date +%s)
  mpirun --allow-run-as-root -np $NP $SU2 $2 > log_$1.txt 2>&1
  local rc=$?; [ $rc -ne 0 ] && { status "stage $1 FAILED rc=$rc"; tail -20 log_$1.txt >> STATUS; exit 3; }
  status "stage $1 done in $(( $(date +%s) - t0 ))s"; }

cfg A.cfg STAGE=A READ_BINARY=NO RESTART_ITER=1 SOLUTION=seed \
    TIME_MARCHING=DUAL_TIME_STEPPING-1ST_ORDER TIME_ITER=$((NA+1)) INNER_ITER=50 CFL=0.5 MUSCL=NO \
    WRT_RESTART=1 WRT_VOL=1000000 WRT_SURF=1000000
run A A.cfg
cfg B.cfg STAGE=B READ_BINARY=YES RESTART_ITER=$((NA+1)) SOLUTION=restart \
    TIME_MARCHING=DUAL_TIME_STEPPING-2ND_ORDER TIME_ITER=$((NSTEP+1)) INNER_ITER=30 CFL=$CFLB MUSCL=YES \
    WRT_RESTART=2500 WRT_VOL=2500 WRT_SURF=50
run B B.cfg
status "running checks"
python3 $SRC/su2/check_su2_phase1.py "$W" $SRC/results_check/$CASE $T0 $P0 101325.0 >> STATUS 2>&1
status "ALL DONE"
