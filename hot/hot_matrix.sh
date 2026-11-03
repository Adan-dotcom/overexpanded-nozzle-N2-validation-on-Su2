#!/bin/bash
# Matriz de diagnostico del arranque caliente, a NPR 10, 900 pasos por variante.
#
# Por que una matriz y no un barrido de dt: el caso caliente diverge (Residual > 10^20)
# en el paso ~303 a NPR 10, y hay CUATRO candidatos sin distinguir. Un barrido de dt
# contesta uno solo. Esta matriz cambia UNA cosa a la vez, igual que `inner_matrix_L3`
# hizo con el caso frio, que es la metodologia que ya funciono.
#
# La variante decisiva es `ideal`: mismo caso con gas ideal de gamma 1.1401 y R 617
# (las propiedades de equilibrio de la mezcla quemada). Si `ideal` corre y `base` no,
# el problema es la TABLA. Si las dos revientan, es la dinamica del gas caliente o el dt.
#
# Uso:  bash hot_matrix.sh <variante>        o  bash hot_matrix.sh todas
#       variantes: n2cold base ideal dt1e-8 dt5e-9 muscl inner60
set -u
SRC=${SRC:-$HOME/dlr-par}
SU2=${SU2:-/mnt/d/SU2/v8.5.0/bin/SU2_CFD}
MESHDIR=${MESHDIR:-$SRC/su2/meshes}
NP=${NP:-6}
WROOT=${WROOT:-$HOME/su2-work/hot_matrix}
PASOS=${PASOS:-900}

PAMB=101325.0; TAMB=300.0; RHOAMB=0.5733
NPR=10
P0=$(python3 -c "print($NPR * $PAMB)")
T0=3265.5                 # T de llama a 10.13 bar (Cantera, equilibrio)
TABLA=LOXLH2_eq_v4.drg
MESH=mesh_L2.su2
# Sutherland de la mezcla quemada (4.35 % de error maximo en 300-3500 K: declarado)
MUREF=1.0086e-05; TREF=300.0; SUTH=773.0
# propiedades de EQUILIBRIO de la mezcla, para la variante de gas ideal
GAM_EQ=1.1401; R_EQ=617.1

corre() {
  local V=$1
  local W=$WROOT/$V
  rm -rf "$W"; mkdir -p "$W"; cd "$W" || return 1
  cp "$MESHDIR/$MESH" . || { echo "falta $MESHDIR/$MESH"; return 1; }
  cp "$MESHDIR/${MESH%.su2}_idmap.npz" . 2>/dev/null
  cp "$SRC/hot/$TABLA" . || { echo "falta $SRC/hot/$TABLA"; return 1; }

  local DT=2.0e-8 MUSCL=NO INNER=30 ORDEN=1ST
  case "$V" in
    base)    ;;
    n2cold)  ;;   # CONTROL: N2 frio ideal, el gas de la campana ya validada
    ideal)   ;;
    dt1e-8)  DT=1.0e-8 ;;
    dt5e-9)  DT=5.0e-9 ;;
    muscl)   MUSCL=YES ;;
    inner60) INNER=60 ;;
    *) echo "variante desconocida: $V"; return 1 ;;
  esac

  local cfg=$V.cfg
  cp "$SRC/su2/phase1_template.cfg" "$cfg" || { echo "  falta la plantilla"; return 1; }
  [ -s "$cfg" ] || { echo "  el cfg quedo vacio"; return 1; }

  sed -i "s|@STAGE@|$V|; s|@READ_BINARY@|NO|; s|@RESTART_ITER@|1|; s|@SOLUTION@|restart|;
          s|@TIME_MARCHING@|DUAL_TIME_STEPPING-${ORDEN}_ORDER|; s|@TIME_ITER@|$((PASOS+1))|;
          s|@INNER_ITER@|$INNER|; s|@CFL@|1.0|; s|@MUSCL@|$MUSCL|;
          s|@WRT_RESTART@|2500|; s|@WRT_VOL@|1000000|; s|@WRT_SURF@|50|;
          s|@T_AMB@|$TAMB|; s|@DT@|$DT|; s|@MESH@|$MESH|; s|@TURB@|SST|" "$cfg"
  python3 - "$cfg" "$P0" "$T0" <<'PY'
import sys
p, P0, T0 = sys.argv[1:4]
# leer ANTES de abrir para escritura: en una linea Python trunca el archivo primero
txt = open(p).read().replace("@P0@", P0).replace("@T0@", T0)
open(p, "w").write(txt)
PY

  if [ "$V" = "n2cold" ]; then
    # CONTROL del propio script: N2 frio ideal a T0 300 K, que es el gas de la campana
    # validada. Si ESTO no corre, el problema es la generacion de configs de este script
    # y ninguna otra variante de la matriz significa nada.
    sed -i "s|^FLUID_MODEL=.*|FLUID_MODEL= IDEAL_GAS|" "$cfg"
    sed -i "s|^GAMMA_VALUE=.*|GAMMA_VALUE= 1.4|" "$cfg"
    sed -i "s|^GAS_CONSTANT=.*|GAS_CONSTANT= 296.8|" "$cfg"
    sed -i "s|^MARKER_RIEMANN=.*|MARKER_RIEMANN= ( INLET, TOTAL_CONDITIONS_PT, $P0, 300.0, 1.0, 0.0, 0.0, OUTLET, STATIC_PRESSURE, $PAMB, 0.0, 0.0, 0.0, 0.0, FARFIELD, STATIC_PRESSURE, $PAMB, 0.0, 0.0, 0.0, 0.0 )|" "$cfg"
  elif [ "$V" = "ideal" ]; then
    # gas ideal con las propiedades de EQUILIBRIO de la mezcla quemada
    sed -i "s|^FLUID_MODEL=.*|FLUID_MODEL= IDEAL_GAS|" "$cfg"
    sed -i "s|^GAMMA_VALUE=.*|GAMMA_VALUE= $GAM_EQ|" "$cfg"
    sed -i "s|^GAS_CONSTANT=.*|GAS_CONSTANT= $R_EQ|" "$cfg"
    grep -q '^GAMMA_VALUE=' "$cfg" || echo "GAMMA_VALUE= $GAM_EQ" >> "$cfg"
    grep -q '^GAS_CONSTANT=' "$cfg" || echo "GAS_CONSTANT= $R_EQ" >> "$cfg"
  else
    sed -i "s|^FLUID_MODEL=.*|FLUID_MODEL= DATADRIVEN_FLUID\nINTERPOLATION_METHOD= LUT\nFILENAMES_INTERPOLATOR= ($TABLA)|" "$cfg"
  fi
  sed -i "s|^CONV_NUM_METHOD_FLOW=.*|CONV_NUM_METHOD_FLOW= ROE|" "$cfg"
  sed -i "s|^VISCOSITY_MODEL=.*|VISCOSITY_MODEL= SUTHERLAND|" "$cfg"
  sed -i "s|^MU_REF=.*|MU_REF= $MUREF|; s|^MU_T_REF=.*|MU_T_REF= $TREF|" "$cfg"
  sed -i "s|^SUTHERLAND_CONSTANT=.*|SUTHERLAND_CONSTANT= $SUTH|" "$cfg"
  sed -i "s|^PRANDTL_LAM=.*|PRANDTL_LAM= 0.62|" "$cfg"
  sed -i "s|^FREESTREAM_PRESSURE=.*|FREESTREAM_PRESSURE= $PAMB|" "$cfg"
  if [ "$V" = "ideal" ] || [ "$V" = "n2cold" ]; then
    # con IDEAL_GAS el estado libre queda SOBRE-especificado si se fijan p, T y rho a la vez:
    # p/(rho R) = 286 K, no 300. SU2 arranca con un estado inconsistente y da NaN en el primer
    # paso. Con gas ideal se fijan solo p y T, y la densidad sale de la ecuacion de estado.
    sed -i "s|^FREESTREAM_TEMPERATURE=.*|FREESTREAM_TEMPERATURE= $TAMB|" "$cfg"
    sed -i "/^FREESTREAM_DENSITY=/d" "$cfg"
  else
    sed -i "s|^FREESTREAM_TEMPERATURE=.*|FREESTREAM_TEMPERATURE= $TAMB\nFREESTREAM_DENSITY= $RHOAMB|" "$cfg"
  fi
  # con fluido no ideal SU2 rechaza MARKER_OUTLET Y MARKER_FAR; con ideal da igual usar Riemann
  sed -i "s|^MARKER_RIEMANN=.*|MARKER_RIEMANN= ( INLET, TOTAL_CONDITIONS_PT, $P0, $T0, 1.0, 0.0, 0.0, OUTLET, STATIC_PRESSURE, $PAMB, 0.0, 0.0, 0.0, 0.0, FARFIELD, STATIC_PRESSURE, $PAMB, 0.0, 0.0, 0.0, 0.0 )|" "$cfg"
  sed -i "/^MARKER_OUTLET=/d; /^MARKER_FAR=/d" "$cfg"
  sed -i "s|^RESTART_SOL=.*|RESTART_SOL= NO|" "$cfg"

  local faltan=$(grep -o '@[A-Z_]*@' "$cfg" | sort -u)
  [ -n "$faltan" ] && { echo "  PLANTILLA INCOMPLETA: $faltan"; return 1; }

  echo "=== $V : dt=$DT MUSCL=$MUSCL INNER=$INNER $( [ "$V" = ideal ] && echo '(GAS IDEAL)' || echo '(LUT)')"
  mpirun --allow-run-as-root -np $NP "$SU2" "$cfg" > log.txt 2>&1
  local rc=$?
  local alcanzados=$(grep -cE "^\| *[0-9]+\|" log.txt)
  local divergio=$(grep -c "has diverged" log.txt)
  echo "  codigo de salida: $rc | lineas de iteracion: $alcanzados | divergio: $divergio"
  python3 "$SRC/su2/decades.py" "history_${V}"*.csv 2>/dev/null | tail -4
  echo "$V rc=$rc div=$divergio" >> "$WROOT/RESUMEN"
}

mkdir -p "$WROOT"; : > "$WROOT/RESUMEN"
if [ "${1:-todas}" = "todas" ]; then
  for v in n2cold ideal base dt1e-8 dt5e-9 muscl inner60; do corre "$v"; done
  echo; echo "=== RESUMEN ==="; cat "$WROOT/RESUMEN"
else
  corre "$1"
fi
