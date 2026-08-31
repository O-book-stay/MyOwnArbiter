#!/bin/bash
set -e
REPO=/home/obooky/myownarbiter
OUT=$REPO/runs/macro_drc
IMG=ghcr.io/librelane/librelane:3.0.8
PDKPATH=$(ls -d /home/obooky/.ciel/ciel/sky130/versions/*/sky130A | sort | tail -1)
PDK_ROOT=$(dirname "$PDKPATH")
SD=$(docker run --rm "$IMG" python3 -c 'import librelane, os; print(os.path.join(os.path.dirname(librelane.__file__), "scripts"))')
mkdir -p "$OUT/reports"

cat > "$OUT/why.tcl" <<'EOF'
gds read $::env(CURRENT_GDS)
load $::env(DESIGN_NAME)
drc on
drc catchup
drc listall why
EOF

docker run --rm \
  -v "$REPO:$REPO" -v /home/obooky/.ciel:/home/obooky/.ciel \
  -w "$OUT" \
  -e CURRENT_GDS="$REPO/src/macro/arbchain.gds" \
  -e DESIGN_NAME=arbchain \
  -e PDK_ROOT="$PDK_ROOT" -e PDKPATH="$PDKPATH" \
  "$IMG" magic -dnull -noconsole \
  -rcfile "$PDKPATH/libs.tech/magic/sky130A.magicrc" \
  "$OUT/why.tcl" 2>&1 | tee "$OUT/drc_why.log" | grep -E 'N-well|diff|width|enclose|Rule' | sort | uniq -c | sort -rn | head -20
