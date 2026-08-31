#!/bin/bash
set -e
REPO=/home/obooky/myownarbiter
OUT=$REPO/runs/macro_drc
IMG=ghcr.io/librelane/librelane:3.0.8
PDKPATH=$(ls -d /home/obooky/.ciel/ciel/sky130/versions/*/sky130A | sort | tail -1)
PDK_ROOT=$(dirname "$PDKPATH")
mkdir -p "$OUT/reports"

cat > "$OUT/why2.tcl" <<'EOF'
gds read $::env(CURRENT_GDS)
load $::env(DESIGN_NAME)
drc euclidean on
drc style drc(full)
drc check
drc catchup
puts "=== spot 1: nwell.1 (0.725,1.545)-(1.055,1.590)um ==="
box 145 309 211 318
drc why
puts "=== spot 2: diff/tap.8 (0.135,1.725)-(0.395,1.770)um ==="
box 27 345 79 354
drc why
puts "=== spot 3: diff/tap.8 right (10.475,1.725)-(10.735,1.770)um ==="
box 2095 345 2147 354
drc why
puts "=== DONE ==="
EOF

docker run --rm \
  -v "$REPO:$REPO" -v /home/obooky/.ciel:/home/obooky/.ciel \
  -w "$OUT" \
  -e CURRENT_GDS="$REPO/src/macro/arbchain.gds" \
  -e DESIGN_NAME=arbchain \
  -e PDK_ROOT="$PDK_ROOT" -e PDKPATH="$PDKPATH" \
  "$IMG" magic -dnull -noconsole \
  -rcfile "$PDKPATH/libs.tech/magic/sky130A.magicrc" \
  "$OUT/why2.tcl" 2>&1 | tee "$OUT/drc_why2.log" | grep -vE '^(Magic|Starting|WARNING|Using|Processing|Switching|Sourcing|2 Magic|Input|The |    ubm|Scaled|Loading|Warning: Calma|Library|Reading|CIF)' | head -60
