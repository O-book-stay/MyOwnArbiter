#!/usr/bin/env python3
# ============================================================
# Normalize the Magic PEX-extracted arbchain netlist for ngspice
# post-layout simulation.
#
# Same LABEL alignment as normalize_layout_spice.py (LVS), with one
# critical difference: the top-level CAPACITORS are kept (the whole
# point of PEX), and their net names get the same aliasing.
#   1. net/port aliases: 'EN'->'launch', 'Q'->'q' (GDS vs LEF names)
#   2. canonical top port list/order from the reference netlist
#
# It does NOT fix or invent any connectivity.
# Raw PEX (arbchain_pex_raw.spice) is kept untouched; the output is
# arbchain_pex.spice.
# ============================================================

import re
import sys

RAW = sys.argv[1]
REF = sys.argv[2]   # reference netlist; supplies the canonical port list
OUT = sys.argv[3]

ALIAS = {"EN": "launch", "Q": "q"}

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
other_elems = []
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
        if not s or s.startswith("*") or s.startswith("."):
            # comments / options / empty: keep comments out, drop the rest
            if s.startswith("*"):
                continue
            continue
        if s.lower().startswith(("x", "c")) or s.startswith("+"):
            top_body.append(s)
        else:
            other_elems.append(s)
    else:
        out_lines.append(ln)

if other_elems:
    sys.exit("ERROR: unexpected top-level elements (extend the script):\n  "
             + "\n  ".join(other_elems[:5]))

# merge '+' continuations first, then alias net names
merged = []
for s in top_body:
    if s.startswith("+"):
        merged[-1] += " " + s[1:].strip()
    else:
        merged.append(s)

body = []
body_nets = set()
for s in merged:
    tok = s.split()
    kind = tok[0][0].upper()
    if kind == "X":            # Xname net... cellname
        nets = [ALIAS.get(n, n) for n in tok[1:-1]]
        body.append(" ".join([tok[0]] + nets + [tok[-1]]))
    elif kind == "C":          # Cname net1 [net2] value
        nets = [ALIAS.get(n, n) for n in tok[1:-1]]
        body.append(" ".join([tok[0]] + nets + [tok[-1]]))
    else:
        sys.exit("ERROR: unsupported element '" + tok[0] + "'")
    body_nets.update(nets)

have = set(ALIAS.get(p, p) for p in top_ports) | body_nets
missing = [p for p in ref_ports if p not in have]
extra = [p for p in (ALIAS.get(p, p) for p in top_ports)
         if p not in ref_ports and p not in body_nets]

final_ports = [p for p in ref_ports]                       # canonical order
final_ports += [p for p in (ALIAS.get(p, p) for p in top_ports)
                if p not in ref_ports]                     # extras, if any

n_x = sum(1 for s in body if s[0].upper() == "X")
n_c = sum(1 for s in body if s[0].upper() == "C")

with open(OUT, "w") as f:
    f.write("* arbchain Magic PEX (C-only), label-normalized for ngspice\n")
    f.write("* aliases applied: "
            + (", ".join(f"{k}->{v}" for k, v in ALIAS.items()) or "none") + "\n")
    for ln in out_lines:            # keep the extracted cell subcircuits
        f.write(ln + "\n")
    f.write(".SUBCKT arbchain " + " ".join(final_ports) + "\n")
    for b in body:
        f.write(b + "\n")
    f.write(".ENDS arbchain\n")

print(f"extracted top ports : {' '.join(top_ports)}")
print(f"after aliasing      : {' '.join(ALIAS.get(p, p) for p in top_ports)}")
print(f"body                : {n_x} X instances, {n_c} capacitors")
print(f"ports attached to body nets: "
      f"{' '.join(p for p in ref_ports if p in body_nets) or '(none)'}")
if missing:
    print(f"DANGLING PORTS (no net in extraction - label missing or "
          f"net has no device): {' '.join(missing)}")
if extra:
    print(f"EXTRA PORTS (not in LEF): {' '.join(extra)}")
print(f"wrote {OUT} with {len(final_ports)} ports, {len(body)} elements")
