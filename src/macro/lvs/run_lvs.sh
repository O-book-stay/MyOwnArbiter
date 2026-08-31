#!/usr/bin/env bash
# ============================================================
# Standalone LVS for the arbchain hard macro.
#
#   layout     <- Magic extraction of src/macro/arbchain.gds
#                 (src/macro/lvs/extract.tcl)
#   schematic  <- generated reference netlist
#                 (src/macro/lvs/gen_arbchain_ref.py; sources:
#                 arbchain.lef interface + RTL topology + PDK pin order)
#   comparison <- netgen -batch source lvs_script.tcl
#                 (librelane scripts/netgen/setup.tcl, NO -blackbox:
#                 the tile flow black-boxes the macro, this does not)
#
# Runs entirely inside the LibreLane container (magic/netgen/python3).
# The repo and the PDK are bind-mounted at their absolute host paths so
# every generated artifact references stable paths.
#
# Usage (WSL):  bash src/macro/lvs/run_lvs.sh
# Results:      runs/macro_lvs/  (PASS = "Circuits match uniquely")
# ============================================================
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LVS="$REPO/src/macro/lvs"
OUT="$REPO/runs/macro_lvs"
IMG="ghcr.io/librelane/librelane:3.0.8"
PDKROOT="/home/obooky/.ciel"
PDKPATH="$(ls -d "$PDKROOT"/ciel/sky130/versions/*/sky130A | sort | tail -1)"
# magicrc's PDK_ROOT is the dir CONTAINING sky130A (not the ~/.ciel root)
PDK_ROOT="$(dirname "$PDKPATH")"
PDK_SPICE="$PDKPATH/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"

mkdir -p "$OUT"

echo "== resolving LibreLane scripts dir =="
SCRIPTS_DIR="$(docker run --rm "$IMG" python3 -c 'import librelane, os; print(os.path.join(os.path.dirname(librelane.__file__), "scripts"))')"
echo "SCRIPTS_DIR=$SCRIPTS_DIR"
echo "PDKPATH=$PDKPATH"

MOUNTS=(-v "$REPO:$REPO" -v "$PDKROOT:$PDKROOT")

echo
echo "== [1/4] Magic extraction of arbchain.gds =="
docker run --rm "${MOUNTS[@]}" \
  -w "$OUT" \
  -e PDK_ROOT="$PDK_ROOT" -e PDKPATH="$PDKPATH" \
  -e CURRENT_GDS="$REPO/src/macro/arbchain.gds" \
  -e DESIGN_NAME=arbchain \
  -e SAVE_SPICE="$OUT/arbchain_lvs.spice" \
  -e EXT_DIR="$OUT/extraction" \
  "$IMG" magic -dnull -noconsole \
  -rcfile "$PDKPATH/libs.tech/magic/sky130A.magicrc" \
  "$LVS/extract.tcl" 2>&1 | tee "$OUT/magic_extract.log"
grep -q "EXTRACT_DONE" "$OUT/magic_extract.log"

echo
echo "== layout-side sanity check =="
echo "ports:    $(awk '/^.subckt arbchain /{print; exit}' "$OUT/arbchain_lvs.spice")"
echo "mux2_1:   $(grep -c ' sky130_fd_sc_hd__mux2_1$' "$OUT/arbchain_lvs.spice") lines"
echo "dlrtp_1:  $(grep -c ' sky130_fd_sc_hd__dlrtp_1$' "$OUT/arbchain_lvs.spice") lines"

echo
echo "== [2/4] Generate reference (schematic) netlist =="
docker run --rm "${MOUNTS[@]}" \
  -w "$OUT" \
  "$IMG" python3 "$LVS/gen_arbchain_ref.py" \
  -o "$OUT/arbchain_ref.spice" --pdk-spice "$PDK_SPICE" | tee "$OUT/gen_ref.log"

echo
echo "== [3/4] Normalize layout labels (EN->launch, Q->q, dangling LEF ports) =="
docker run --rm "${MOUNTS[@]}" \
  -w "$OUT" \
  "$IMG" python3 "$LVS/normalize_layout_spice.py" \
  "$OUT/arbchain_lvs.spice" "$OUT/arbchain_ref.spice" \
  "$OUT/arbchain_lvs_norm.spice" | tee "$OUT/normalize.log"

echo
echo "== [4/4] netgen LVS =="
: > "$OUT/empty_env.tcl"
sed -e "s|@OUT@|$OUT|g" \
    -e "s|@PDK_SPICE@|$PDK_SPICE|g" \
    -e "s|@SETUP@|$SCRIPTS_DIR/netgen/setup.tcl|g" \
    -e "s|@NETGEN_SETUP@|$PDKPATH/libs.tech/netgen/sky130A_setup.tcl|g" \
    -e "s|@TCL_ENV_IN@|$OUT/empty_env.tcl|g" \
    "$LVS/lvs_script.tcl.in" > "$OUT/lvs_script.tcl"

docker run --rm "${MOUNTS[@]}" \
  -w "$OUT" \
  -e PDK_ROOT="$PDK_ROOT" -e PDKPATH="$PDKPATH" \
  -e _TCL_ENV_IN="$OUT/empty_env.tcl" \
  -e NETGEN_SETUP="$PDKPATH/libs.tech/netgen/sky130A_setup.tcl" \
  "$IMG" netgen -batch source "$OUT/lvs_script.tcl" 2>&1 | tee "$OUT/netgen.log"
grep -q "NETGEN_LVS_SCRIPT_DONE" "$OUT/netgen.log"

echo
if grep -q "Circuits match uniquely" "$OUT/netgen.log"; then
  echo "LVS PASS: Circuits match uniquely  (report: $OUT/lvs.netgen.rpt)"
else
  echo "LVS FAIL — inspect $OUT/netgen.log and $OUT/lvs.netgen.rpt"
  docker run --rm "${MOUNTS[@]}" -w "$OUT" \
    "$IMG" python3 "$LVS/analyze_connectivity.py" \
    "$OUT/arbchain_lvs_norm.spice" | tee "$OUT/connectivity.rpt" || true
  exit 1
fi
