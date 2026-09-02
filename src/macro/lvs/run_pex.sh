#!/usr/bin/env bash
# ============================================================
# Standalone C-only PEX for the arbchain hard macro.
#
#   layout     <- Magic parasitic extraction of src/macro/arbchain.gds
#                 (lvs/extract_pex.tcl; capacitance ON, resistance OFF)
#   reference  <- generated reference netlist
#                 (lvs/gen_arbchain_ref.py; canonical port list/order)
#   normalize  <- lvs/normalize_pex_spice.py (port aliases + keep caps)
#
# Runs inside the LibreLane container (magic/python3), same mount
# pattern as lvs/run_lvs.sh.
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
PDK_SPICE="$PDKPATH/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"

mkdir -p "$OUT"

MOUNTS=(-v "$REPO:$REPO" -v "$PDKROOT:$PDKROOT")

echo
echo "== [1/3] Magic PEX extraction (C-only) of arbchain.gds =="
docker run --rm "${MOUNTS[@]}" \
  -w "$OUT" \
  -e PDK_ROOT="$PDK_ROOT" -e PDKPATH="$PDKPATH" \
  -e CURRENT_GDS="$REPO/src/macro/arbchain.gds" \
  -e DESIGN_NAME=arbchain \
  -e SAVE_SPICE="$OUT/arbchain_pex_raw.spice" \
  -e EXT_DIR="$OUT/extraction" \
  "$IMG" magic -dnull -noconsole \
  -rcfile "$PDKPATH/libs.tech/magic/sky130A.magicrc" \
  "$LVS/extract_pex.tcl" 2>&1 | tee "$OUT/magic_pex.log"
grep -q "EXTRACT_PEX_DONE" "$OUT/magic_pex.log"

echo
echo "== [2/3] Generate reference netlist (canonical ports) =="
docker run --rm "${MOUNTS[@]}" \
  -w "$OUT" \
  "$IMG" python3 "$LVS/gen_arbchain_ref.py" \
  -o "$OUT/arbchain_ref.spice" --pdk-spice "$PDK_SPICE" | tee "$OUT/gen_ref.log"

echo
echo "== [3/3] Normalize ports/aliases (keeps capacitors) =="
docker run --rm "${MOUNTS[@]}" \
  -w "$OUT" \
  "$IMG" python3 "$LVS/normalize_pex_spice.py" \
  "$OUT/arbchain_pex_raw.spice" "$OUT/arbchain_ref.spice" \
  "$OUT/arbchain_pex.spice" | tee "$OUT/normalize_pex.log"

echo
echo "== layout-side sanity =="
echo "X instances:      $(grep -c '^X' "$OUT/arbchain_pex.spice")"
echo "capacitors:       $(grep -cE '^C' "$OUT/arbchain_pex_raw.spice") raw / $(grep -cE '^C' "$OUT/arbchain_pex.spice") normalized"
echo "top subckt line:  $(awk '/^\.subckt arbchain /{print; exit}' "$OUT/arbchain_pex.spice")"

echo
echo "PEX_DONE -> $OUT/arbchain_pex.spice"
