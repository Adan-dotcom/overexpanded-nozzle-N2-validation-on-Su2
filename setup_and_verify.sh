#!/bin/bash
# setup_and_verify.sh — run this FIRST on the second PC, inside WSL Ubuntu.
# 1) installs dependencies, 2) locates SU2 8.5.0, 3) runs a ~1 min smoke test.
# It changes nothing outside your home dir and /tmp.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
export SRC="$HERE"
ok() { echo "  OK   $*"; }
bad() { echo "  FAIL $*"; FAILED=1; }
FAILED=0

echo "== 1. dependencies (checked, not installed - this script never calls sudo)"
if python3 -c "import numpy, scipy, matplotlib" 2>/dev/null; then ok "python numpy/scipy/matplotlib"
else bad "python packages -> run:  pip3 install numpy scipy matplotlib"; fi
if command -v mpirun >/dev/null; then ok "mpirun $(mpirun --version | head -1 | awk '{print $NF}')"
else bad "mpirun missing -> run:  sudo apt update && sudo apt install -y openmpi-bin libopenmpi-dev python3-pip"; fi

echo "== 2. SU2"
: "${SU2:=/mnt/d/SU2/v8.5.0/bin/SU2_CFD}"
if [ ! -x "$SU2" ]; then
  for c in /opt/SU2/bin/SU2_CFD $HOME/SU2/bin/SU2_CFD $(command -v SU2_CFD); do [ -x "$c" ] && SU2="$c" && break; done
fi
if [ -x "$SU2" ]; then
  V=$("$SU2" --help 2>&1 | grep -o 'v8\.[0-9.]*' | head -1)
  [ "$V" = "v8.5.0" ] && ok "SU2 $V at $SU2" || echo "  WARN SU2 version $V (expected v8.5.0) at $SU2"
else
  bad "SU2_CFD not found. Copy the folder D:\\SU2\\v8.5.0 from the other PC, or set SU2=/path/to/SU2_CFD"
fi
export SU2

echo "== 3. files"
for f in dlr_par_real_geometry.lua su2/run_steady.sh su2/steady_template.cfg su2/make_seed.py \
         su2/check_su2_phase1.py su2/meshes/mesh_L2.su2 su2/meshes/mesh_L2_idmap.npz; do
  [ -f "$HERE/$f" ] && ok "$f" || bad "missing $f"
done

[ $FAILED -eq 0 ] || { echo; echo "Fix the FAIL lines above before running anything else."; exit 1; }

echo "== 4. smoke test (~1 min): 30+30 iterations on the small L0 mesh, 2 ranks"
bash "$HERE/su2/run_steady.sh" smoke_check mesh_L0.su2 50 2 30 30 2>&1 | tail -6
W=$HOME/su2-work/smoke_check
if grep -q "ALL DONE" "$W/STATUS" 2>/dev/null; then
  python3 "$HERE/su2/check_su2_phase1.py" "$W" /tmp/smoke_check_out 300 5066250 101325 >/dev/null 2>&1 \
    && ok "post-processing works" || bad "post-processing failed"
  echo; echo "SETUP OK. The smoke test is meaningless physically (60 iterations)."
  echo "Next, the real run (~1-2 h):"
  echo "  SRC=$HERE SU2=$SU2 bash $HERE/su2/run_steady.sh steadyL2_NPR50 mesh_L2.su2 50 6"
else
  bad "smoke test did not finish - see $W/log_*.txt"
fi
