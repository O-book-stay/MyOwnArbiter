#!/usr/bin/env bash
# ============================================================
# Standalone R+C PEX for the arbchain hard macro.
#
#   layout <- Magic parasitic extraction of src/macro/arbchain.gds
#             (lvs/extract_pex.tcl: extract + extresist +
#             `ext2spice extresist on`; capacitance ON, resistance ON)
#
# The output is a FLAT top-level transistor netlist (no .subckt):
# 404 devices + distributed wire R (extresist patches) + substrate/
# coupling C. Interface nets keep their label names (ch[i], launch,
# arb_rst_n, q, VPWR, VGND), so no port normalization is needed —
# the testbench (src/macro/sim/arbchain_postsim.spice) drives them
# directly by name.
#
# Runs inside the LibreLane container (magic), same mount pattern
# as lvs/run_lvs.sh.
#
# Usage (WSL):  bash src/macro/lvs/run_pex.sh
# Results:      runs/macro_pex/arbchain_pex.spice   (ngspice-ready)
# ============================================================
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LVS="$REPO/src/macro/lvs"
OUT="$REPO/runs/macro_pex"
IMG="ghcr.io/librelane/librelane:3.0.8"
PDKROOT="/home/obooky/.ciel"
PDKPATH="$(ls -d "$PDKROOT"/ciel/sky130/versions/*/sky130A | sort | tail -1)"
# magicrc's PDK_ROOT is the dir CONTAINING sky130A (not the ~/.ciel root)
PDK_ROOT="$(dirname "$PDKPATH")"

mkdir -p "$OUT"

MOUNTS=(-v "$REPO:$REPO" -v "$PDKROOT:$PDKROOT")

echo
echo "== [1/2] Magic PEX extraction (R+C) of arbchain.gds =="
docker run --rm "${MOUNTS[@]}" \
  -w "$OUT" \
  -e PDK_ROOT="$PDK_ROOT" -e PDKPATH="$PDKPATH" \
  -e CURRENT_GDS="$REPO/src/macro/arbchain.gds" \
  -e DESIGN_NAME=arbchain \
  -e SAVE_SPICE="$OUT/arbchain_pex.spice" \
  -e EXT_DIR="$OUT/extraction" \
  "$IMG" magic -dnull -noconsole \
  -rcfile "$PDKPATH/libs.tech/magic/sky130A.magicrc" \
  "$LVS/extract_pex.tcl" 2>&1 | tee "$OUT/magic_pex.log"
grep -q "EXTRESIST_OK" "$OUT/magic_pex.log"
grep -q "EXTRACT_PEX_DONE" "$OUT/magic_pex.log"

echo
echo "== [2/2] Sanity check =="
SPICE="$OUT/arbchain_pex.spice"
n_x=$(grep -c '^X' "$SPICE" || true)
n_r=$(grep -cE '^R' "$SPICE" || true)
n_c=$(grep -cE '^C' "$SPICE" || true)
echo "transistors (X):  $n_x   (expect 404 = 32x mux2_1 + 1x dlrtp_1)"
echo "resistors (R):    $n_r   (expect >0; extresist distributed wire R)"
echo "capacitors (C):   $n_c   (expect >0; substrate + coupling)"
if [ "$n_r" -eq 0 ]; then
  echo "ERROR: no resistors - ext2spice extresist on did not take effect"
  exit 1
fi
n_subckt=$(grep -ci '^\.subckt' "$SPICE" || true)
echo "subckt lines:     $n_subckt   (expect 0: flat netlist)"

echo
echo "interface nets present:"
fail=0
for net in "ch[0]" "ch[1]" "ch[2]" "ch[3]" "ch[4]" "ch[5]" "ch[6]" "ch[7]" \
           "ch[8]" "ch[9]" "ch[10]" "ch[11]" "ch[12]" "ch[13]" "ch[14]" "ch[15]" \
           launch arb_rst_n q VPWR VGND; do
  c=$(grep -cF " $net " "$SPICE" || true)
  printf "  %-10s %s\n" "$net" "$c"
  if [ "$c" -eq 0 ]; then
    echo "  ERROR: net $net missing from the PEX netlist"
    fail=1
  fi
done
if [ "$fail" -ne 0 ]; then exit 1; fi

echo
echo "PEX_DONE -> $SPICE"
