#!/usr/bin/env python3
"""Connectivity audit of the (normalized) extracted arbchain netlist.

Lists every net of the top-level arbchain subckt classified by pin
fanout: single-pin nets are opens (routing missing in the GDS),
2-pin nets are plain chain links, >2-pin nets are expected branches
(PG rails, launch, stage outputs feeding two next-stage inputs).
Usage: analyze_connectivity.py [netlist.spice]
"""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/obooky/myownarbiter/runs/macro_lvs/arbchain_lvs.spice"

lines = open(path).read().splitlines()
# join continuations
joined, buf = [], ""
for ln in lines:
    if ln.startswith("+"):
        buf += " " + ln[1:].strip()
    else:
        if buf:
            joined.append(buf)
        buf = ln.strip()
if buf:
    joined.append(buf)

# top-level arbchain subckt body
body, inside = [], False
for ln in joined:
    s = ln.lower()
    if s.startswith(".subckt arbchain"):
        inside = True
        continue
    if inside and s.startswith(".ends"):
        break
    if inside and ln.lower().startswith("x"):
        body.append(ln.split())

# cell pin order from the cell subckts in the same file
pinof = {}
cur = None
for ln in joined:
    s = ln.lower()
    m = re.match(r"^\.subckt\s+(\S+)\s+(.*)$", s)
    if m and m.group(1) != "arbchain":
        cur = m.group(1)
        pinof[cur] = m.group(2).split()
    elif cur and s.startswith(".ends"):
        cur = None

fanout = {}
insts = []
for tok in body:
    name = tok[-1]
    pins = pinof[name]
    nets = tok[1:-1]
    assert len(nets) == len(pins), (tok[0], name)
    insts.append((tok[0], name))
    for p, n in zip(pins, nets):
        fanout.setdefault(n, []).append(f"{tok[0]}/{p}")

print(f"instances: {len(insts)}")
print(f"distinct nets: {len(fanout)}")

singles = {n: v for n, v in fanout.items() if len(v) == 1}
multi = {n: v for n, v in fanout.items() if len(v) > 2}
print(f"\n== nets with exactly ONE pin attached (opens): {len(singles)}")
for n, v in sorted(singles.items()):
    print(f"  {n}: {v[0]}")

print(f"\n== nets with MORE than 2 pins (branches): {len(multi)}")
for n, v in sorted(multi.items(), key=lambda kv: -len(kv[1])):
    print(f"  {n} ({len(v)}): {' '.join(v[:6])}{' ...' if len(v) > 6 else ''}")

two = {n: v for n, v in fanout.items() if len(v) == 2}
print(f"\n== nets with exactly 2 pins: {len(two)}")
for n, v in sorted(two.items()):
    print(f"  {n}: {v[0]} <-> {v[1]}")
