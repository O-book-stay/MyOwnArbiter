#!/usr/bin/env python3
# ============================================================
# Normalize the Magic-extracted arbchain netlist for netgen LVS.
#
# This is LABEL alignment only -- it does NOT fix or invent any
# connectivity:
#   1. net/port aliases: the GDS labels the stage-0 launch net 'EN'
#      and the arbiter output 'Q' (uppercase); the LEF/RTL contract
#      calls them 'launch' and 'q'.  Renamed accordingly.
#   2. missing labels: LEF ports with no label anywhere in the GDS
#      (arb_rst_n as of 2026-08-31) are added as dangling ports so
#      netgen can report the unconnected net explicitly.
#
# Raw extraction (arbchain_lvs.spice) is kept untouched; the output
# is arbchain_lvs_norm.spice.
# ============================================================

import re
import sys

RAW = sys.argv[1]
REF = sys.argv[2]   # reference netlist; supplies the canonical port list
OUT = sys.argv[3]

ALIAS = {"EN": "launch", "Q": "q"}

# canonical port order from the reference (generated from the LEF)
ref_ports = None
for ln in open(REF):
    m = re.match(r"^\.SUBCKT\s+arbchain\s+(.*)$", ln.strip(), re.I)
    if m:
        ref_ports = m.group(1).split()
        break
if ref_ports is None:
    sys.exit("ERROR: no .SUBCKT arbchain found in " + REF)

lines = open(RAW).read().splitlines()

# split into cell sections and the top arbchain section
out_lines = []
in_top = False
top_ports = []
top_body = []
for ln in lines:
    s = ln.strip()
    m = re.match(r"^\.SUBCKT\s+arbchain(\s+.*)?$", s, re.I)
    if m and not in_top:
        in_top = True
        top_ports = (m.group(1) or "").split()
        continue
    if in_top and re.match(r"^\.ENDS(\s+arbchain)?$", s, re.I):
        in_top = False
        continue
    if in_top:
        if s.lower().startswith("x") or s.startswith("+"):
            top_body.append(s)
        # (anything else in the top section is dropped)
    else:
        out_lines.append(ln)

renamed = [ALIAS.get(p, p) for p in top_ports]

# merge '+' continuations first, then alias net names
merged = []
for s in top_body:
    if s.startswith("+"):
        merged[-1] += " " + s[1:].strip()
    else:
        merged.append(s)
body = []
for s in merged:
    tok = s.split()
    if tok[0].upper().startswith("X"):
        nets = [ALIAS.get(n, n) for n in tok[1:-1]]
        body.append(" ".join([tok[0]] + nets + [tok[-1]]))
    else:
        body.append(s)

# every net name appearing in the body (a port name matching a body net
# attaches to it; a port with no net anywhere stays dangling)
body_nets = set()
for s in merged:
    tok = s.split()
    if tok[0].upper().startswith("X"):
        body_nets.update(ALIAS.get(n, n) for n in tok[1:-1])

have = set(renamed) | body_nets
missing = [p for p in ref_ports if p not in have]
extra = [p for p in renamed if p not in ref_ports and p not in body_nets]

final_ports = [p for p in ref_ports]            # canonical order
final_ports += [p for p in renamed if p not in ref_ports]  # extras, if any

with open(OUT, "w") as f:
    f.write("* arbchain Magic extraction, label-normalized for netgen\n")
    f.write("* aliases applied: " +
            (", ".join(f"{k}->{v}" for k, v in ALIAS.items()) or "none") + "\n")
    for ln in out_lines:            # keep the extracted cell subcircuits
        f.write(ln + "\n")
    f.write(".SUBCKT arbchain " + " ".join(final_ports) + "\n")
    for b in body:
        f.write(b + "\n")
    f.write(".ENDS arbchain\n")

print(f"extracted top ports : {' '.join(top_ports)}")
print(f"after aliasing      : {' '.join(renamed)}")
print(f"ports attached to body nets: "
      f"{' '.join(p for p in ref_ports if p in body_nets) or '(none)'}")
if missing:
    print(f"DANGLING PORTS (no net in extraction — label missing or "
          f"net has no device): {' '.join(missing)}")
if extra:
    print(f"EXTRA PORTS (not in LEF): {' '.join(extra)}")
print(f"wrote {OUT} with {len(final_ports)} ports, {len(body)} instances")
