#!/usr/bin/env bash
# ============================================================
# Per-stage race-skew measurement (the 16 w's) of the arbchain
# macro, from the R+C PEX netlist. Three single-pulse ngspice runs
# (challenge 0000 / ffff / a5a5) + topology mapping + analysis.
#
#   ngspice runs on the WSL host; python3 on the host too.
#   netlist: runs/macro_pex/arbchain_pex.spice (run_pex.sh first)
#
# Usage (WSL):  bash src/macro/sim/run_postsim.sh
# Results:      runs/macro_sim/postsim_<hex>.log, chain_diag.txt
# ============================================================
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SIM="$REPO/src/macro/sim"
PEX="$REPO/runs/macro_pex/arbchain_pex.spice"
OUT="$REPO/runs/macro_sim"
MAP="$REPO/runs/macro_pex/chain_map.json"
PDKPATH="$(ls -d /home/obooky/.ciel/ciel/sky130/versions/*/sky130A | sort | tail -1)"

if [ ! -f "$PEX" ]; then
  echo "ERROR: $PEX missing - run 'bash src/macro/lvs/run_pex.sh' first"
  exit 1
fi
mkdir -p "$OUT"

echo "== [1/3] chain topology map =="
python3 "$SIM/map_chain.py" --pex "$PEX" -o "$MAP"

echo
echo "== [2/3] three single-pulse runs (0000 / ffff / a5a5) =="
for CH in 0000 ffff a5a5; do
  python3 "$SIM/gen_postsim_tb.py" --map "$MAP" --pex "$PEX" \
      --pdk "$PDKPATH" --challenge "$CH" --out "$OUT/postsim_$CH.spice"
  echo "-- ngspice challenge $CH ..."
  (cd "$OUT" && ngspice -b "postsim_$CH.spice" > "postsim_$CH.log" 2>&1)
  if ! grep -q "^qval" "$OUT/postsim_$CH.log"; then
    echo "ERROR: challenge $CH did not produce results - see $OUT/postsim_$CH.log"
    exit 1
  fi
  grep -E "^qval" "$OUT/postsim_$CH.log"
done

echo
echo "== [3/3] per-stage skew analysis =="
python3 "$SIM/analyze_chain.py" --map "$MAP" \
    --log "0000=$OUT/postsim_0000.log" \
    --log "ffff=$OUT/postsim_ffff.log" \
    --log "a5a5=$OUT/postsim_a5a5.log" \
    --out "$OUT/chain_diag.txt"

echo
echo "POSTSIM_DONE -> $OUT/chain_diag.txt"
