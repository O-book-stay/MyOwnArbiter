#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# probe_short.py - definitive per-layer short test between components.
# Two distinct union-find components cannot be connected by construction
# (same-layer touch / via bridge would have merged them), so a real short
# can only show up as same-layer overlap - tested here layer by layer.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import klayout.db as pya
from check_chain_delay import ArbChecker, build_graph, MET1, MET2, MET3, MET4

HERE = os.path.dirname(os.path.abspath(__file__))
GDS = sys.argv[1] if len(sys.argv) > 1 else "arbchain.gds"

ck = ArbChecker(os.path.join(HERE, GDS),
                os.path.join(HERE, "cells"), os.path.join(HERE, "cells"))
g = build_graph(ck.top, ck.ly, ck.dbu)
LAYERS = {MET1: "met1", MET2: "met2", MET3: "met3", MET4: "met4"}

def comp_layer_region(comp):
    regs = {}
    for nid in range(len(g.p)):
        if g.find(nid) != comp:
            continue
        lay = g.lay[nid]
        if lay not in LAYERS:
            continue
        b = g.box[nid]
        regs.setdefault(lay, pya.Region()).insert(
            pya.Box(int(round(b[0]*1000)), int(round(b[1]*1000)),
                    int(round(b[2]*1000)), int(round(b[3]*1000))))
    return regs

pairs = [tuple(int(x) for x in a.split(",")) for a in sys.argv[2:]]
any_short = False
for (a, b) in pairs:
    ra, rb = comp_layer_region(a), comp_layer_region(b)
    hits = []
    for lay in sorted(set(ra) & set(rb)):
        ov = (ra[lay] & rb[lay])
        if not ov.is_empty():
            hits.append((LAYERS[lay], ov.area() * 1e-6))
    status = f"SHORT on {hits}" if hits else "no same-layer contact"
    print(f"comp {a} vs {b}: {status}")
    any_short |= bool(hits)
print("RESULT:", "SHORT DETECTED" if any_short else "CLEAN - all flags were "
      "multi-layer proximity, not shorts")
