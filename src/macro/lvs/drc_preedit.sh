#!/bin/bash
set -e
REPO=/home/obooky/myownarbiter
OUT=$REPO/runs/macro_drc_preedit
IMG=ghcr.io/librelane/librelane:3.0.8
PDKPATH=$(ls -d /home/obooky/.ciel/ciel/sky130/versions/*/sky130A | sort | tail -1)
PDK_ROOT=$(dirname "$PDKPATH")
SD=$(docker run --rm "$IMG" python3 -c 'import librelane, os; print(os.path.join(os.path.dirname(librelane.__file__), "scripts"))')
mkdir -p "$OUT" "$OUT/reports"
git --git-dir="$REPO/.git" show HEAD:src/macro/arbchain.gds > "$OUT/arbchain_committed.gds"

cat > "$OUT/env_in.tcl" <<EOF
set ::env(MAGIC_DRC_USE_GDS) 1
set ::env(CURRENT_GDS) $OUT/arbchain_committed.gds
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
  "$SD/magic/wrapper.tcl" 2>&1 | grep -E 'COUNT|divided'
echo "---- rule breakdown ----"
grep -B1 -A2 'um ' "$OUT/reports/drc.magic.rpt" | grep -vE '^--$' | head -8
grep -c 'um ' "$OUT/reports/drc.magic.rpt" || true
