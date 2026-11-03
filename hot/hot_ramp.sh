#!/bin/bash
# Arranque por RAMPA del caso caliente LOX/LH2 a NPR 33 (la misma NPR del caso frio
# validado, para que la comparacion aisle el efecto del gas y no mezcle NPR).
#
# Por que una rampa: arrancar con la camara a NPR 33 contra un campo inicializado a
# presion ambiente mete un salto de 33:1 en la frontera de entrada; medido el 3-nov-2026,
# eso deja la caida del residuo DENTRO del paso en 0.0007 decadas (criterio: >= 1.2).
# A NPR 10 desde cero la mediana de los ultimos pasos es ~1.43 y mejorando. La rampa
# sube la NPR por etapas, reiniciando de la anterior.
#
# Uso:  bash hot_ramp.sh [ETAPA]     con ETAPA en {r1, r2, r3, prod, todo}
set -u
SRC=${SRC:-$HOME/dlr-par}                  # raiz del repo en la torre
SU2=${SU2:-/mnt/d/SU2/v8.5.0/bin/SU2_CFD}
MESHDIR=${MESHDIR:-$SRC/su2/meshes}
NP=${NP:-6}
W=${W:-$HOME/su2-work/hot_npr33}
PAMB=101325.0
TAMB=300.0
RHOAMB=0.5733          # mezcla quemada a 300 K y 1 atm (Cantera). Ver la nota del ambiente.
DT=2.0e-8              # mismo CFL acustico que el frio en L2 (a_caliente ~ 4.5x a_frio)
TABLA=LOXLH2_eq_v4.drg
MESH=mesh_L2.su2

# Etapas de la rampa: NPR, T0 de llama a esa presion (Cantera, equilibrio), pasos
#   la T0 cambia con la presion: mas presion suprime la disociacion y sube la llama
declare -A NPR=( [r1]=10 [r2]=20 [r3]=33 [prod]=33 )
declare -A T0=(  [r1]=3265.5 [r2]=3347.7 [r3]=3406.2 [prod]=3406.2 )
declare -A PASOS=( [r1]=5000 [r2]=5000 [r3]=5000 [prod]=${PROD_STEPS:-150000} )
declare -A ORDEN=( [r1]=1ST [r2]=1ST [r3]=1ST [prod]=2ND )

mkdir -p "$W"; cd "$W" || exit 1
cp "$MESHDIR/$MESH" . 2>/dev/null || { echo "falta $MESHDIR/$MESH"; exit 1; }
cp "$MESHDIR/${MESH%.su2}_idmap.npz" . 2>/dev/null
cp "$SRC/hot/$TABLA" . || { echo "falta $SRC/hot/$TABLA"; exit 1; }

# Sutherland ajustado a la viscosidad de la mezcla quemada (Cantera). El ajuste tiene
# 4.3 % de error maximo en 300-3500 K: es el numero mas flojo de la cadena y se declara.
MUREF=1.0086e-05; TREF=300.0; SUTH=773.0

etapa() {
  local E=$1 PREV=$2
  local P0=$(python3 -c "print(${NPR[$E]} * $PAMB)")
  local N=${PASOS[$E]}
  local cfg=$E.cfg
  echo "=== etapa $E : NPR ${NPR[$E]}  p0 $P0 Pa  T0 ${T0[$E]} K  $N pasos  BDF-${ORDEN[$E]}"
  cp "$SRC/su2/phase1_template.cfg" "$cfg" || { echo "  falta la plantilla $SRC/su2/phase1_template.cfg"; return 1; }
  [ -s "$cfg" ] || { echo "  el cfg quedo vacio"; return 1; }

  local TM="DUAL_TIME_STEPPING-1ST_ORDER"
  [ "${ORDEN[$E]}" = "2ND" ] && TM="DUAL_TIME_STEPPING-2ND_ORDER"
  local RSOL=YES RITER=1
  if [ -z "$PREV" ]; then RSOL=NO; fi

  sed -i "s|@STAGE@|$E|; s|@READ_BINARY@|NO|; s|@RESTART_ITER@|$RITER|; s|@SOLUTION@|restart|;
          s|@TIME_MARCHING@|$TM|; s|@TIME_ITER@|$((N+1))|;
          s|@INNER_ITER@|30|; s|@CFL@|1.0|; s|@MUSCL@|NO|;
          s|@WRT_RESTART@|2500|; s|@WRT_VOL@|1000000|; s|@WRT_SURF@|50|;
          s|@T_AMB@|$TAMB|; s|@DT@|$DT|; s|@MESH@|$MESH|; s|@TURB@|SST|" "$cfg"
  python3 - "$cfg" "$P0" "${T0[$E]}" <<'PY'
import sys
p, P0, T0 = sys.argv[1:4]
# OJO: leer ANTES de abrir para escritura. En una sola linea Python abre con "w"
# primero y trunca el archivo antes de leerlo (fallo ya cometido en esta campana).
txt = open(p).read().replace("@P0@", P0).replace("@T0@", T0)
open(p, "w").write(txt)
PY

  sed -i "s|^FLUID_MODEL=.*|FLUID_MODEL= DATADRIVEN_FLUID\nINTERPOLATION_METHOD= LUT\nFILENAMES_INTERPOLATOR= ($TABLA)|" "$cfg"
  sed -i "s|^CONV_NUM_METHOD_FLOW=.*|CONV_NUM_METHOD_FLOW= ROE|" "$cfg"     # SLAU2 asume gas ideal
  sed -i "s|^VISCOSITY_MODEL=.*|VISCOSITY_MODEL= SUTHERLAND|" "$cfg"
  sed -i "s|^MU_REF=.*|MU_REF= $MUREF|; s|^MU_T_REF=.*|MU_T_REF= $TREF|" "$cfg"
  sed -i "s|^SUTHERLAND_CONSTANT=.*|SUTHERLAND_CONSTANT= $SUTH|" "$cfg"
  sed -i "s|^PRANDTL_LAM=.*|PRANDTL_LAM= 0.62|" "$cfg"
  sed -i "s|^FREESTREAM_PRESSURE=.*|FREESTREAM_PRESSURE= $PAMB|" "$cfg"
  sed -i "s|^FREESTREAM_TEMPERATURE=.*|FREESTREAM_TEMPERATURE= $TAMB\nFREESTREAM_DENSITY= $RHOAMB|" "$cfg"
  # con fluido no ideal SU2 rechaza MARKER_OUTLET Y MARKER_FAR (CConfig.cpp:4299 y 4304)
  sed -i "s|^MARKER_RIEMANN=.*|MARKER_RIEMANN= ( INLET, TOTAL_CONDITIONS_PT, $P0, ${T0[$E]}, 1.0, 0.0, 0.0, OUTLET, STATIC_PRESSURE, $PAMB, 0.0, 0.0, 0.0, 0.0, FARFIELD, STATIC_PRESSURE, $PAMB, 0.0, 0.0, 0.0, 0.0 )|" "$cfg"
  sed -i "/^MARKER_OUTLET=/d; /^MARKER_FAR=/d" "$cfg"
  sed -i "s|^RESTART_SOL=.*|RESTART_SOL= $RSOL|" "$cfg"
  if [ -n "$PREV" ]; then
    cp "$PREV" solution.dat 2>/dev/null || cp "$PREV" solution.csv 2>/dev/null
    sed -i "s|^SOLUTION_FILENAME=.*|SOLUTION_FILENAME= solution|" "$cfg"
  fi

  local faltan=$(grep -o '@[A-Z_]*@' "$cfg" | sort -u)
  [ -n "$faltan" ] && { echo "PLANTILLA INCOMPLETA: $faltan"; return 1; }

  mpirun --allow-run-as-root -np $NP "$SU2" "$cfg" > log_$E.txt 2>&1
  local rc=$?
  echo "  codigo de salida: $rc"
  # SENAL POSITIVA de exito, no ausencia de error
  local ult=$(ls -t restart_*.dat restart_*.csv 2>/dev/null | head -1)
  echo "  ultimo reinicio: ${ult:-NINGUNO}"
  echo "  archivos de pared: $(ls wall_*.csv 2>/dev/null | wc -l)"
  python3 "$SRC/su2/decades.py" "history_${E}"*.csv 2>/dev/null || \
    echo "  (sin decades.py: mide la caida por paso a mano antes de confiar en la etapa)"
  [ -n "$ult" ] && echo "$ult" > ULTIMO_$E
  return $rc
}

case "${1:-todo}" in
  r1)   etapa r1 "" ;;
  r2)   etapa r2 "$(cat ULTIMO_r1)" ;;
  r3)   etapa r3 "$(cat ULTIMO_r2)" ;;
  prod) etapa prod "$(cat ULTIMO_r3)" ;;
  todo) etapa r1 "" && etapa r2 "$(cat ULTIMO_r1)" && etapa r3 "$(cat ULTIMO_r2)" \
        && etapa prod "$(cat ULTIMO_r3)" ;;
  *) echo "etapa desconocida: $1"; exit 1 ;;
esac
