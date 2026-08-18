#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# check_arbchain.py
#
# Poor-man's LVS for the generated arbchain macro.
#
# Scope: validates the *routing drawn by the generator* against the
# standard-cell pin positions taken from the LEF files.  The cells'
# own internal connectivity is not analysed here (the per-cell GDS
# used locally may be an abstract view; the real cells are validated
# by the LibreLane DRC/LVS flow).
#
# Method:
#   * conductive graph = pin li1 rects (LEF) + every shape drawn by
#     the generator (from arbchain_routing.json), with via cuts
#     bridging adjacent metal layers, via union-find
#   * the intended netlist comes from the generator's net model
#   * verify each intended net is one component, no two nets share
#     a component, and no net touches VDD/VSS
#
# Usage: python check_arbchain.py <arbchain_routing.json> \
#            --cell-gds-dir DIR --cell-lef-dir DIR
# ============================================================

import argparse
import importlib.util
import json
import os
import sys

import klayout.db as pya

HERE = os.path.dirname(os.path.abspath(__file__))


def load_gen(path):
    spec = importlib.util.spec_from_file_location("gen_arbchain", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class UnionFind:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("routing_json")
    ap.add_argument("--cell-gds-dir", default=None)
    ap.add_argument("--cell-lef-dir", default=None)
    args = ap.parse_args()

    m = load_gen(os.path.join(HERE, "gen_arbchain.py"))
    STAGES = m.STAGES
    PITCH = m.PITCH
    YOFF = m.YOFF

    gds_dir, lef_dir = m.ensure_cells(args.cell_gds_dir, args.cell_lef_dir)

    mux = m.Cell(m.MUX_LEF, os.path.join(gds_dir, "sky130_fd_sc_hd__mux2_1.gds"),
                 os.path.join(lef_dir, "sky130_fd_sc_hd__mux2_1.lef"))
    latch = m.Cell(m.LATCH_LEF, os.path.join(gds_dir, "sky130_fd_sc_hd__dlrtp_1.gds"),
                   os.path.join(lef_dir, "sky130_fd_sc_hd__dlrtp_1.lef"))

    with open(args.routing_json) as fh:
        drawn = json.load(fh)

    # ------------------------------------------------------------------
    # conductive graph: merge same-layer shapes, then bridge via cuts
    # ------------------------------------------------------------------
    uf = UnionFind(0)
    polys = {}
    nid = 0

    def add_merged(layer, boxes):
        nonlocal nid
        reg = pya.Region()
        for b in boxes:
            reg.insert(pya.Box(int(b[0] * 1000), int(b[1] * 1000),
                               int(b[2] * 1000), int(b[3] * 1000)))
        reg.merge()
        polys.setdefault(layer, [])
        for po in reg.each():
            polys[layer].append((nid, pya.Region(po)))
            uf.p.append(nid)
            nid += 1

    drawn_by_layer = {}
    for shp in drawn:
        drawn_by_layer.setdefault(tuple(shp["layer"]), []).append(shp["box"])

    for layer, boxes in drawn_by_layer.items():
        if layer in ((67, 20),):
            continue  # li1 handled as pin nodes below
        add_merged(layer, boxes)

    # pin li1 nodes (LEF positions); record the node that contains the
    # access point (the one the via-stack connects to)
    def add_pin(cell, trans, pin, ax, ay):
        nonlocal nid
        reg = pya.Region()
        for r in m.pin_rects_um(cell, trans, pin):
            reg.insert(pya.Box(int(r[0] * 1000), int(r[1] * 1000),
                               int(r[2] * 1000), int(r[3] * 1000)))
        reg.merge()
        polys.setdefault((67, 20), [])
        nodes = []
        for po in reg.each():
            polys[(67, 20)].append((nid, pya.Region(po)))
            uf.p.append(nid)
            nodes.append(nid)
            nid += 1
        p = pya.Point(int(ax * 1000), int(ay * 1000))
        for nd in nodes:
            for po in polys[(67, 20)][-len(nodes):][nodes.index(nd)][1].each():
                if po.inside(p):
                    return nd
        return nodes[0] if nodes else None

    # bridge layers through via cuts
    def bridge():
        for cut, la, lb in (((67, 44), (67, 20), (68, 20)),
                            ((68, 44), (68, 20), (69, 20)),
                            ((69, 44), (69, 20), (70, 20)),
                            ((70, 44), (70, 20), (71, 20))):
            if cut not in polys or la not in polys or lb not in polys:
                continue
            for (i, reg) in polys[cut]:
                for (j, rega) in polys[la]:
                    if not (reg & rega).is_empty():
                        uf.union(i, j)
                for (j, regb) in polys[lb]:
                    if not (reg & regb).is_empty():
                        uf.union(i, j)

    bridge()

    def comp_of(node_id):
        return uf.find(node_id) if node_id is not None else None

    # ------------------------------------------------------------------
    # intended netlist (access points identical to generator)
    # ------------------------------------------------------------------
    nets = {}   # netname -> list of node ids

    def add(netname, cell, trans, pin, y):
        pt = m.safe_access(cell, trans, pin, y)
        if pt is None:
            print(f"  !! no access for net {netname} pin {pin} y={y}")
            return
        nd = add_pin(cell, trans, pin, pt[0], pt[1])
        nets.setdefault(netname, []).append(nd)

    def row(g):
        return m.EV if g % 2 == 0 else m.OD

    tc0 = row(0)
    add("ch[0]", mux, m.top_trans(0), "S", YOFF + tc0["ch"])
    add("ch[0]", mux, m.bot_trans(0), "S", YOFF + tc0["ch"])
    for g in range(1, STAGES):
        yp = (g - 1) * PITCH + YOFF
        yc = g * PITCH + YOFF
        tp = row(g - 1)
        tc = row(g)
        add(f"top[{g}]", mux, m.top_trans(g - 1), "X", yp + tp["x"])
        add(f"top[{g}]", mux, m.top_trans(g), "A0", yc + tc["a0"])
        add(f"top[{g}]", mux, m.bot_trans(g), "A1", yc + tc["a1b"])
        add(f"bot[{g}]", mux, m.bot_trans(g - 1), "X", yp + tp["x"])
        add(f"bot[{g}]", mux, m.top_trans(g), "A1", yc + tc["a1t"])
        add(f"bot[{g}]", mux, m.bot_trans(g), "A0", yc + tc["a0"])
        add(f"ch[{g}]", mux, m.top_trans(g), "S", yc + tc["ch"])
        add(f"ch[{g}]", mux, m.bot_trans(g), "S", yc + tc["ch"])
    add("launch", mux, m.top_trans(0), "A0", YOFF + tc0["a0"])
    add("launch", mux, m.bot_trans(0), "A0", YOFF + tc0["a0"])
    add("launch", mux, m.top_trans(0), "A1", YOFF + tc0["a1t"])
    add("launch", mux, m.bot_trans(0), "A1", YOFF + tc0["a1b"])
    ylat = STAGES * PITCH + YOFF
    add("top[%d]" % STAGES, mux, m.top_trans(STAGES - 1), "X", ylat - PITCH + row(STAGES - 1)["x"])
    add("top[%d]" % STAGES, latch, m.latch_trans(ylat), "D", ylat + 1.2)
    add("bot[%d]" % STAGES, mux, m.bot_trans(STAGES - 1), "X", ylat - PITCH + row(STAGES - 1)["x"])
    add("bot[%d]" % STAGES, latch, m.latch_trans(ylat), "GATE", ylat + 1.0)
    add("q", latch, m.latch_trans(ylat), "Q", ylat + 0.38)
    add("arb_rst_n", latch, m.latch_trans(ylat), "RESET_B", ylat + 0.38)

    # bridge again (pins added after first bridge)
    bridge()

    # power components: find VDD/VSS rail components from the drawn rails
    def comp_on_rail(x, y):
        for (i, reg) in polys.get((68, 20), []):
            for po in reg.each():
                if po.inside(pya.Point(int(x * 1000), int(y * 1000))):
                    return uf.find(i)
        return None

    vdd_comp = comp_on_rail(0.5, YOFF + 2.72)
    vss_comp = comp_on_rail(0.5, YOFF)
    print(f"VDD comp={vdd_comp} VSS comp={vss_comp}")

    bad = 0
    net_comp = {}
    for name, node_ids in sorted(nets.items()):
        comps_found = set()
        for nd in node_ids:
            c = comp_of(nd)
            if c is None:
                print(f"NET {name}: missing component")
                bad += 1
            else:
                comps_found.add(c)
        if len(comps_found) != 1:
            bad += 1
            print(f"NET {name}: comps={comps_found} (expect 1)")
        else:
            c = comps_found.pop()
            net_comp[name] = c
            if vdd_comp is not None and c == vdd_comp:
                bad += 1
                print(f"NET {name}: SHORTED TO VDD")
            if vss_comp is not None and c == vss_comp:
                bad += 1
                print(f"NET {name}: SHORTED TO VSS")
    seen = {}
    for name, c in net_comp.items():
        if c in seen and seen[c] != name:
            bad += 1
            print(f"SHORT: nets {seen[c]} and {name} share component {c}")
        seen[c] = name
    print()
    print("FAILED nets:", bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
