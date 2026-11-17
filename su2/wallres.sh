#!/bin/bash
# wallres.sh  --  wall-resolution study at NPR 33 (cold N2, SST, same numerics as the campaign).
#
# Why: the three meshes at NPR 33 give 54.74 / 62.25 / 74.81 mm (L1/L2/L3) and the jumps GROW
# with refinement, so Richardson does not apply. The meshes differ in y+ regime (20 / 9.7 / ~2)
# and L1 and L2 compute a closed bubble (RSS) where the experiment is FSS. Two meshes test this:
#
#   L22 : L2 streamwise grid, L3 wall-normal grid (first cell 1.9 um).      55 050 cells
#         If x_sep jumps from 62 mm towards ~75 mm, the wall resolution was the cause.
#   L33 : L3 streamwise grid, wall-normal 4.4x finer than L3 (0.43 um).    120 000 cells
#         If x_sep stays at ~74.8 mm, L3 is converged where it matters.
#
#   bash su2/wallres.sh L22                       seed: su2/seed_L2_NPR33_at_2p5ms.csv.gz
#   bash su2/wallres.sh L33 /path/restart_N.csv   seed: a SETTLED L3 restart at NPR 33 (CSV)
#   RESUME=1 bash su2/wallres.sh L22|L33          resume stage B from the newest restart pair
#   PROBE=1  bash su2/wallres.sh ...              only the dt probe, no production run
#
# The time step is not assumed. A probe runs 300 BDF2 steps at each candidate dt, largest first,
# and takes the first one whose WORST step drops >= 1.2 decades. Everything is written to STATUS.
set -u
HERE=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
SRC=${SRC:-$(dirname "$HERE")}                 # repo root (has su2/)
SU2=${SU2:-/mnt/d/SU2/v8.5.0/bin/SU2_CFD}
NP=${NP:-6}
LV=${1:?usage: wallres.sh L22|L33 [SEED_RESTART.csv]}
case $LV in
  L22) DTS=${DTS:-"1.0e-7 5.0e-8"};  T_MS=${T_MS:-10}; SEED=${2:-$SRC/su2/seed_L2_NPR33_at_2p5ms.csv.gz} ;;
  L33) DTS=${DTS:-"5.0e-8 2.5e-8"};  T_MS=${T_MS:-5};  SEED=${2:-} ;;
  *) echo "unknown level $LV" >&2; exit 1 ;;
esac
MESH=mesh_$LV.su2
T0=300.0; P_AMB=101325.0; NPR=33
P0=$(python3 -c "print(f'{$NPR*$P_AMB:.1f}')")
N_PROBE=${N_PROBE:-300}
CASE=w_${LV}_NPR33
W=${WORK:-$HOME/su2-work}/$CASE; OUT=$SRC/results/$CASE

if pgrep -x SU2_CFD >/dev/null 2>&1 && [ "${ALLOW_CONCURRENT:-0}" != 1 ]; then
  echo "ERROR: SU2_CFD is already running. Not sharing cores." >&2; exit 9; fi
mkdir -p "$W" "$OUT"; cd "$W" || exit 1
# sealed copy: editing the shared script while it runs makes bash jump lines
if [ "${SEALED:-0}" != 1 ]; then
  cp "$HERE/wallres.sh" "$W/_runner.sh"
  SEALED=1 SRC=$SRC exec bash "$W/_runner.sh" "$@"
fi
status() { echo "$(date -Is) $*" | tee -a STATUS; }
[ "${RESUME:-0}" = 1 ] || : > STATUS

cfg() { local out=$1 dt=$2; shift 2; cp $SRC/su2/phase1_template.cfg "$out"
  for kv in "$@"; do sed -i "s|@${kv%%=*}@|${kv#*=}|g" "$out"; done
  sed -i "s|@T_AMB@|300.0|; s|@P0@|$P0|; s|@T0@|$T0|; s|@DT@|$dt|; s|@MESH@|$MESH|; s|@TURB@|SST|" "$out"
  grep -q '@' "$out" && { status "unfilled placeholder in $out"; exit 2; }; }
run() { status "stage $1 start"; local t0=$(date +%s)
  mpirun --allow-run-as-root -np $NP $SU2 "$2" > log_$1.txt 2>&1
  local rc=$?; status "stage $1 rc=$rc in $(( $(date +%s) - t0 ))s"; return $rc; }
# worst-step decades of a history file; prints "min median", or "0 0" if unusable
dec() { python3 $SRC/su2/decades.py "$1" 2>/dev/null \
        | sed -n 's/.*mediana \([-0-9.]*\) | min \([-0-9.]*\).*/\2 \1/p' | grep . || echo "0 0"; }
finish() {
  status "post-processing"
  python3 $SRC/su2/decades.py "history_B*.csv" >> STATUS 2>&1
  python3 $SRC/su2/wall_series.py . $DT "$OUT/serie_full.csv" >> STATUS 2>&1
  python3 $SRC/su2/traj.py "$OUT/serie_full.csv" 100 >> STATUS 2>&1
  python3 $SRC/su2/topology.py . x "$OUT/tau_w_final.csv" >> STATUS 2>&1
  python3 $SRC/su2/yplus.py . >> STATUS 2>&1
  cp -f STATUS history_*.csv *.cfg "$OUT"/ 2>/dev/null
  status "DONE -- derived files in $OUT (git add results/$CASE; do NOT add wall_*.csv or restarts)"
  cp -f STATUS "$OUT"/
}

# ---------------- resume ----------------
if [ "${RESUME:-0}" = 1 ]; then
  [ -f B.cfg ] && [ -f DT_CHOSEN ] || { status "RESUME: no B.cfg / DT_CHOSEN here"; exit 1; }
  DT=$(cat DT_CHOSEN)
  # newest pair BY DATE, never by number
  R=${R:-$(ls -t restart_*.dat 2>/dev/null | sed 's/restart_0*\([0-9]*\)\.dat/\1/' \
           | awk '$1%2500==0 && $1>0' | head -1)}
  [ -n "${R:-}" ] || { status "RESUME: no restart at a multiple of 2500"; exit 1; }
  [ -f "restart_$(printf %05d $((R-1))).dat" ] || { status "RESUME: restart $((R-1)) missing (BDF2 needs it)"; exit 1; }
  status "RESUME stage B from step $R (dt=$DT)"
  sed "s|^RESTART_ITER=.*|RESTART_ITER= $((R+1))|; s|history_B|history_B_r$R|" B.cfg > B_r$R.cfg
  if ! diff <(grep -vE 'RESTART_ITER|CONV_FILENAME' B.cfg) <(grep -vE 'RESTART_ITER|CONV_FILENAME' B_r$R.cfg) >/dev/null; then
    status "RESUME: B_r$R.cfg differs from B.cfg beyond the restart point -- aborted"; exit 2; fi
  run B_r$R B_r$R.cfg || { tail -20 log_B_r$R.txt >> STATUS; exit 3; }
  finish; exit 0
fi

# ---------------- seed ----------------
[ -n "$SEED" ] && [ -f "$SEED" ] || { status "seed not found: '$SEED'"; exit 1; }
cp $SRC/su2/meshes/$MESH $SRC/su2/meshes/${MESH%.su2}_idmap.npz . || { status "mesh $MESH missing"; exit 1; }
case "$SEED" in *.gz) zcat "$SEED" > seed_src.csv ;; *) cp "$SEED" seed_src.csv ;; esac
status "case=$CASE mesh=$MESH seed=$SEED NPR=$NPR np=$NP candidates dt=[$DTS] record=${T_MS} ms"
python3 $SRC/su2/interp_seed.py seed_src.csv $MESH seed_00000.csv >> STATUS 2>&1 || { status "interp_seed failed"; exit 1; }

# ---------------- dt probe ----------------
DT=
for d in $DTS; do
  P=probe_$d; mkdir -p $P
  ( cd $P && ln -sf ../$MESH . && ln -sf ../seed_00000.csv . ) || exit 1
  cfg $P/A.cfg $d STAGE=A READ_BINARY=NO RESTART_ITER=1 SOLUTION=seed \
      TIME_MARCHING=DUAL_TIME_STEPPING-1ST_ORDER TIME_ITER=4 INNER_ITER=50 CFL=0.5 MUSCL=NO \
      WRT_RESTART=1 WRT_VOL=1000000 WRT_SURF=1000000
  cfg $P/B.cfg $d STAGE=B READ_BINARY=YES RESTART_ITER=4 SOLUTION=restart \
      TIME_MARCHING=DUAL_TIME_STEPPING-2ND_ORDER TIME_ITER=$((N_PROBE+4)) INNER_ITER=30 CFL=2.0 MUSCL=YES \
      WRT_RESTART=1000000 WRT_VOL=1000000 WRT_SURF=1000000
  ok=1
  ( cd $P && mpirun --allow-run-as-root -np $NP $SU2 A.cfg > log_A.txt 2>&1 \
          && mpirun --allow-run-as-root -np $NP $SU2 B.cfg > log_B.txt 2>&1 ) || ok=0
  read mn md < <(dec "$P/history_B*.csv")
  nan=$(grep -ci "nan" $P/history_B*.csv 2>/dev/null | head -1)
  status "probe dt=$d : rc_ok=$ok  worst-step decades=$mn  median=$md  nan_lines=${nan:-?}"
  if [ $ok = 1 ] && [ "${nan:-1}" = 0 ] && python3 -c "import sys; sys.exit(0 if $mn >= 1.2 else 1)"; then
    DT=$d; break; fi
done
[ -n "$DT" ] || { status "NO candidate dt meets >= 1.2 decades on every step. STOP and report; do not force it."; cp -f STATUS "$OUT"/; exit 4; }
echo $DT > DT_CHOSEN
N=$(python3 -c "print(round($T_MS*1e-3/$DT))")
status "dt chosen = $DT  ->  $N steps for $T_MS ms"
cp -f STATUS "$OUT"/
[ "${PROBE:-0}" = 1 ] && { status "PROBE only -- stopping here"; exit 0; }

# ---------------- production ----------------
cfg A.cfg $DT STAGE=A READ_BINARY=NO RESTART_ITER=1 SOLUTION=seed \
    TIME_MARCHING=DUAL_TIME_STEPPING-1ST_ORDER TIME_ITER=4 INNER_ITER=50 CFL=0.5 MUSCL=NO \
    WRT_RESTART=1 WRT_VOL=1000000 WRT_SURF=1000000
run A A.cfg || { tail -20 log_A.txt >> STATUS; exit 3; }
cfg B.cfg $DT STAGE=B READ_BINARY=YES RESTART_ITER=4 SOLUTION=restart \
    TIME_MARCHING=DUAL_TIME_STEPPING-2ND_ORDER TIME_ITER=$((N+1)) INNER_ITER=30 CFL=2.0 MUSCL=YES \
    WRT_RESTART=2500 WRT_VOL=2500 WRT_SURF=50
run B B.cfg || { tail -20 log_B.txt >> STATUS; cp -f STATUS "$OUT"/; exit 3; }
finish
