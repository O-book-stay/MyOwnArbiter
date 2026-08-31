#!/bin/bash
# Standalone Magic DRC for the arbchain macro (AGENTS.md recipe).
set -e
REPO=/home/obooky/myownarbiter
OUT=$REPO/runs/macro_drc
IMG=ghcr.io/librelane/librelane:3.0.8
PDKPATH=$(ls -d /home/obooky/.ciel/ciel/sky130/versions/*/sky130A | sort | tail -1)
PDK_ROOT=$(dirname "$PDKPATH")
mkdir -p "$OUT" "$OUT/reports"

SD=$(docker run --rm "$IMG" python3 -c 'import librelane, os; print(os.path.join(os.path.dirname(librelane.__file__), "scripts"))')

cat > "$OUT/env_in.tcl" <<EOF
set ::env(MAGIC_DRC_USE_GDS) 1
set ::env(CURRENT_GDS) $REPO/src/macro/arbchain.gds
set ::env(DESIGN_NAME) arbchain
set ::env(STEP_DIR) $OUT
set ::env(SCRIPTS_DIR) $SD
set ::env(PDK_ROOT) $PDK_ROOT
set ::env(PDKPATH) $PDKPATH
EOF

docker run --rm \
  -v "$REPO:$REPO" -v /home/obooky/.ciel:/home/obooky/.ciel \
  -w "$OUT" \
  -e _TCL_ENV_IN="$OUT/env_in.tcl" \
  -e _MAGIC_SCRIPT="$SD/magic/drc.tcl" \
  -e PDK_ROOT="$PDK_ROOT" -e PDKPATH="$PDKPATH" \
  "$IMG" magic -dnull -noconsole \
  -rcfile "$PDKPATH/libs.tech/magic/sky130A.magicrc" \
  "$SD/magic/wrapper.tcl" 2>&1 | tee "$OUT/magic_drc.log"

echo "---- DRC summary ----"
grep -E 'COUNT|DRC errors|violat' "$OUT/magic_drc.log" | tail -10 || true
ls "$OUT" | head
