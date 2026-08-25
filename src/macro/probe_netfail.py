#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# probe_netfail.py - inspect which metal belongs to the components that
# check_chain_delay.py flags, to judge real-short vs checker artifact.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import klayout.db as pya
from check_chain_delay import (CellGeom, ArbChecker, build_graph,
                               LI1, MET1, MET2, MET3, MET4, MCON,
                               VIA1L, VIA2L, VIA3L)

HERE = os.path.dirname(os.path.abspath(__file__))
GDS = sys.argv[1] if len(sys.argv) > 1 else "arbchain.gds"

ck = ArbChecker(os.path.join(HERE, GDS),
                os.path.join(HERE, "cells"), os.path.join(HERE, "cells"))
g = build_graph(ck.top, ck.ly, ck.dbu)

def show(comp):
    print(f"--- comp {comp} ---")
    for nid in range(len(g.p)):
        if g.find(nid) != comp:
            continue
        b = g.box[nid]
        lay = g.lay[nid]
        nm = lay if isinstance(lay, tuple) else ("CUT", lay[1]) if isinstance(lay, tuple) else lay
        print(f"   {str(nm):<10} ({b[0]:.3f},{b[1]:.3f})-({b[2]:.3f},{b[3]:.3f})")

for c in (int(a) for a in sys.argv[2:]):
    show(c)

# also dump the exact pin access points used by the failing nets
rows = ck.rows()
N = len(rows)
latch = ck.latch_inst()
print("== pin access points ==")
def pt(cell, inst, pin):
    p = ck.access(cell, inst, pin)
    return f"({p[0]:.3f},{p[1]:.3f})" if p else "None"

cy, l, r = rows[N-1]          # last row = stage N-1
print("stage15 S left :", pt(ck.mux, l, "S"), " right:", pt(ck.mux, r, "S"))
print("latch D/GATE/Q/RST:",
      pt(ck.latch, latch, "D"), pt(ck.latch, latch, "GATE"),
      pt(ck.latch, latch, "Q"), pt(ck.latch, latch, "RESET_B"))
cy, l, r = rows[0]
print("stage0 A0/A1 L :", pt(ck.mux, l, "A0"), pt(ck.mux, l, "A1"),
      " R:", pt(ck.mux, r, "A0"), pt(ck.mux, r, "A1"))
