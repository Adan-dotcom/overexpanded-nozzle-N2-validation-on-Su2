#!/bin/bash
# extend.sh  --  continue a finished URANS record until it SETTLES, then stop by itself.
#
# Written for the L3 NPR 33 record (p11, 200 000 steps at 5e-8 s = 10 ms of extension), which at
# 9.6 ms was still drifting (x_p50 74.7 -> ~89.5 mm, accelerating) and is RSS by the tau_w audit.
# The question is where it ends up: the measured shutdown (RSS) branch at NPR 33 is 103.3 mm, the
# startup (FSS) branch 75.7 mm. Instead of fixed 10 ms blocks, this runs in chunks and checks after
# every chunk whether it has settled.
#
#   bash su2/extend.sh /root/su2-work/<p11 run dir>          new extension from its newest restart
#   RESUME=1 bash su2/extend.sh /root/su2-work/<p11 run dir> continue an interrupted extension
#
# SETTLED means ALL of:
#   - at least T_MIN_MS of extension;
#   - linear-fit drift of x_p50 below DRIFT mm/ms in EACH of the last two WIN_MS windows
#     (the old rule compared only the two ends of the second half and was fooled by a pause);
#   - the same tau_w topology verdict (FSS / RSS / ...) on every restart of the last WIN_MS.
# It stops at T_MAX_MS regardless and says NOT SETTLED.
#
# Time step: the probe tries DTS (largest first, 300 steps each) and keeps the first whose WORST
# step drops >= 1.2 decades. Larger dt than 1e-7 is NOT offered on L3: the 22 Sep test gave a
# worst step of 1.0 decades and up to 10 % instantaneous wall-pressure error at 2.5e-7.
# If no candidate passes it stops (exit 4): report it, do not force it.
set -u
HERE=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
SRC=${SRC:-$(dirname "$HERE")}                 # repo root (has su2/)
SU2=${SU2:-/mnt/d/SU2/v8.5.0/bin/SU2_CFD}
NP=${NP:-6}
FROM=${1:?usage: extend.sh SOURCE_RUN_DIR [CASE]}
FROM=$(readlink -f "$FROM")
MESH=${MESH:-mesh_L3.su2}
NPR=${NPR:-33}
LV=${MESH#mesh_}; LV=${LV%.su2}
CASE=${2:-ext_${LV}_NPR$NPR}
DTS=${DTS:-"1.0e-7 5.0e-8"}
N_PROBE=${N_PROBE:-300}
CHUNK=${CHUNK:-2500}
SURF=${SURF:-50}                                # wall output every SURF steps (as the campaign)
T_MIN_MS=${T_MIN_MS:-2}; T_MAX_MS=${T_MAX_MS:-10}; WIN_MS=${WIN_MS:-1}; DRIFT=${DRIFT:-0.5}
T0=300.0; P_AMB=101325.0
P0=$(python3 -c "print(f'{$NPR*$P_AMB:.1f}')")
W=${WORK:-$HOME/su2-work}/$CASE; OUT=$SRC/results/$CASE

if pgrep -x SU2_CFD >/dev/null 2>&1 && [ "${ALLOW_CONCURRENT:-0}" != 1 ]; then
  echo "ERROR: SU2_CFD is already running. Wait for it to finish; not sharing cores." >&2; exit 9; fi
mkdir -p "$W" "$OUT"; cd "$W" || exit 1
if [ "${SEALED:-0}" != 1 ]; then           # sealed copy: editing the repo script mid-run is safe
  cp "$HERE/extend.sh" "$W/_runner.sh"
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
# worst/median within-step decades of ONE history file -> "min median" ("0 0" if unusable)
dec() { python3 $SRC/su2/decades.py "$1" 2>/dev/null \
        | sed -n 's/.*mediana \([-0-9.]*\) | min \([-0-9.]*\).*/\2 \1/p' | grep . || echo "0 0"; }
ok_ge() { python3 -c "import sys; sys.exit(0 if float('$1') >= float('$2') else 1)"; }
rfile() { printf "restart_%05d.%s" "$1" "$2"; }
publish() { cp -f STATUS CHECKS serie.csv "$OUT"/ 2>/dev/null; cp -f topo_*.txt "$OUT"/ 2>/dev/null; }

if [ "${RESUME:-0}" != 1 ]; then
  # ---------------- seed: newest restart of the source run, BY DATE ----------------
  S=$(ls -t "$FROM"/restart_*.csv 2>/dev/null | head -1)
  [ -n "$S" ] || { status "no restart_*.csv in $FROM"; exit 1; }
  for f in "$MESH" "${MESH%.su2}_idmap.npz"; do
    cp "$FROM/$f" . 2>/dev/null || cp "$SRC/su2/meshes/$f" . || { status "missing $f"; exit 1; }
  done
  cp "$S" seed_00000.csv || exit 1
  status "case=$CASE from=$FROM seed=$(basename $S) ($(date -r "$S" -Is)) mesh=$MESH NPR=$NPR np=$NP"
  status "rules: dt candidates [$DTS], chunk $CHUNK steps, settled = drift < $DRIFT mm/ms in each of the last 2 x $WIN_MS ms + same topology over the last $WIN_MS ms, min $T_MIN_MS ms, max $T_MAX_MS ms"
  python3 $SRC/su2/topology.py . seed_00000.csv topo_seed.csv > topo_seed.txt 2>&1
  status "topology of the seed: $(grep VEREDICTO topo_seed.txt || echo '?')"

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
    H=$(ls $P/history_B*.csv 2>/dev/null | head -1)
    read mn md < <(dec "${H:-none}")
    nan=$(cat $P/history_B*.csv 2>/dev/null | grep -ci nan)
    status "probe dt=$d : rc_ok=$ok  worst-step decades=$mn  median=$md  nan_lines=$nan"
    if [ $ok = 1 ] && [ "$nan" = 0 ] && ok_ge "$mn" 1.2; then DT=$d; break; fi
  done
  [ -n "$DT" ] || { status "NO candidate dt has >= 1.2 decades on every step. STOP; report, do not force."; publish; exit 4; }
  echo $DT > DT_CHOSEN
  status "dt chosen = $DT"
  publish
  [ "${PROBE:-0}" = 1 ] && { status "PROBE only -- stopping here"; exit 0; }

  # ---------------- stage A: 3 first-order steps to build the BDF2 time levels ----------------
  cfg A.cfg $DT STAGE=A READ_BINARY=NO RESTART_ITER=1 SOLUTION=seed \
      TIME_MARCHING=DUAL_TIME_STEPPING-1ST_ORDER TIME_ITER=4 INNER_ITER=50 CFL=0.5 MUSCL=NO \
      WRT_RESTART=1 WRT_VOL=1000000 WRT_SURF=1000000
  run A A.cfg || { tail -20 log_A.txt >> STATUS; publish; exit 3; }
  R=4                                   # stage B starts reading restarts 3 and 2
  : > CHECKS
else
  [ -f DT_CHOSEN ] || { status "RESUME: no DT_CHOSEN here ($W)"; exit 1; }
  DT=$(cat DT_CHOSEN)
  # newest checkpoint BY DATE whose BDF2 partner (N-1) exists
  R=
  for f in $(ls -t restart_*.dat 2>/dev/null); do
    n=$(echo $f | sed 's/restart_0*\([0-9]*\)\.dat/\1/')
    [ $((n % CHUNK)) = 0 ] && [ "$n" -gt 0 ] && [ -f "$(rfile $((n-1)) dat)" ] && { R=$((n+1)); break; }
  done
  [ -n "$R" ] || { status "RESUME: no complete checkpoint pair at a multiple of $CHUNK"; exit 1; }
  status "RESUME from step $((R-1)) (dt=$DT)"
fi

# ---------------- production in chunks, with the settling check after each ----------------
NMAX=$(python3 -c "print(round($T_MAX_MS*1e-3/$DT))")
while :; do
  E=$(( (R / CHUNK + 1) * CHUNK )); [ $E -gt $NMAX ] && E=$NMAX
  [ $R -gt $E ] && break
  cfg B_$E.cfg $DT STAGE=B READ_BINARY=YES RESTART_ITER=$R SOLUTION=restart \
      TIME_MARCHING=DUAL_TIME_STEPPING-2ND_ORDER TIME_ITER=$((E+1)) INNER_ITER=30 CFL=2.0 MUSCL=YES \
      WRT_RESTART=$CHUNK WRT_VOL=$CHUNK WRT_SURF=$SURF
  run B_$E B_$E.cfg || { tail -20 log_B_$E.txt >> STATUS; publish; exit 3; }
  for x in "$(rfile $E dat)" "$(rfile $((E-1)) dat)" "$(rfile $E csv)"; do
    [ -f "$x" ] || { status "chunk to $E: $x was not written -- stopping (positive signal missing)"; publish; exit 5; }
  done
  H=$(ls -t history_B*.csv | head -1); read mn md < <(dec "$H")
  python3 $SRC/su2/topology.py . "$(rfile $E csv)" "topo_$E.csv" > topo_$E.txt 2>&1
  V=$(sed -n 's/^VEREDICTO: *\([A-Z]*\).*/\1/p' topo_$E.txt); V=${V:-?}
  python3 $SRC/su2/wall_series.py . $DT serie.csv > /dev/null 2>&1
  echo "$E $mn $md $V" >> CHECKS
  verdict=$(python3 - "$DT" "$T_MIN_MS" "$WIN_MS" "$DRIFT" <<'PY'
import csv, sys
import numpy as np
dt, tmin, win, lim = map(float, sys.argv[1:5])
rows = list(csv.DictReader(open("serie.csv")))
t = np.array([float(r["t_s"]) for r in rows]) * 1e3
x = np.array([float(r["x_p50_rt"]) for r in rows]) * 10.0
chk = [l.split() for l in open("CHECKS")]
T = t[-1]
def slope(a, b):
    m = (t >= a) & (t <= b)
    return np.polyfit(t[m], x[m], 1)[0] if m.sum() > 5 else np.nan
s1, s2 = slope(T - win, T), slope(T - 2 * win, T - win)
steps_win = win * 1e-3 / dt
topo = [c[3] for c in chk if float(c[0]) * dt * 1e3 >= T - win]
same = len(topo) >= 2 and len(set(topo)) == 1
ok = T >= tmin and abs(s1) < lim and abs(s2) < lim and same
print("t=%.3f ms  x_p50=%.2f mm  drift last %g ms %+.2f, previous %+.2f mm/ms  topology last %g ms %s  -> %s"
      % (T, x[-1], win, s1, s2, win, ",".join(topo) or "?", "SETTLED" if ok else "not settled"))
PY
)
  status "step $E  decades min $mn median $md  topology $V | $verdict"
  publish
  if ! ok_ge "$mn" 1.2; then
    status "a step dropped < 1.2 decades -- watch it; stopping only if the median also fails"
    ok_ge "$md" 1.2 || { status "median < 1.2 decades: STOP and report, do not force"; exit 6; }
  fi
  case "$verdict" in *"-> SETTLED"*) status "SETTLED -- done. Push results/$CASE"; publish; exit 0 ;; esac
  [ $E -ge $NMAX ] && { status "reached T_MAX = $T_MAX_MS ms: NOT SETTLED. Push results/$CASE and report"; publish; exit 0; }
  R=$((E+1))
done
