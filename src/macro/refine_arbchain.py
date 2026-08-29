#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# refine_arbchain.py -- programmatic DRC fixes on top of the hand-drawn
# arbchain macro.  Source of truth: my_own_arbchain.gds (signal routing
# frozen).  Pipeline: snap off-grid shapes, rename CH labels (same
# contract as fix_my_own_arbchain.py), then rule-targeted fixes.
#
# Usage:
#   python refine_arbchain.py --fix-via5a --fix-via24a [--report-mcon]
#
# Output: arbchain.gds (consumed by gen_lef_gds.py and the tt flow).
import os
import sys

import klayout.db as pya

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "my_own_arbchain.gds")
DST = os.path.join(HERE, "arbchain.gds")
GRID = 5

LI1 = (67, 20)
MET1 = (68, 20)
MET2 = (69, 20)
MET3 = (70, 20)
MET4 = (71, 20)
MCON = (67, 44)
VIA1 = (68, 44)
VIA2 = (69, 44)
VIA3 = (70, 44)
LABEL_M2 = (69, 5)
LABEL_M4 = (71, 5)


def snap(v):
    return round(v / GRID) * GRID


def snap_all(ly, cell):
    n = 0
    for li in list(ly.layer_indexes()):
        shapes = cell.shapes(li)
        for s in list(shapes.each()):
            if s.is_box():
                b = s.box
                if (b.left % GRID or b.bottom % GRID or
                        b.right % GRID or b.top % GRID):
                    shapes.replace(s, pya.Box(snap(b.left), snap(b.bottom),
                                              snap(b.right), snap(b.top)))
                    n += 1
            elif s.is_polygon():
                raw = list(s.polygon.each_point_hull())
                if any(p.x % GRID or p.y % GRID for p in raw):
                    pts = [pya.Point(snap(p.x), snap(p.y)) for p in raw]
                    if len(set((p.x, p.y) for p in pts)) < 3:
                        continue
                    shapes.replace(s, pya.Polygon(pts))
                    n += 1
    return n


def rename_ch_labels(ly, cell):
    lab = ly.layer(*LABEL_M2)
    chans = [s for s in cell.shapes(lab).each()
             if s.is_text() and s.text.string == "CH"]
    chans.sort(key=lambda s: s.text.trans.disp.y)
    assert len(chans) == 16, f"expected 16 CH labels, got {len(chans)}"
    for i, s in enumerate(chans):
        t = s.text
        t.string = f"ch[{i}]"
        s.text = t
    return len(chans)


class FlatGraph:
    def __init__(self, ly, top):
        self.ly = ly
        self.top = top
        self.regions = {}
        self.uf = []

    def find(self, x):
        p = self.uf
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.uf[rb] = ra

    def build(self, layers):
        for sem in layers:
            li = self.ly.find_layer(*sem)
            reg = pya.Region()
            if li is not None:
                it = self.top.begin_shapes_rec(li)
                while not it.at_end():
                    reg.insert(it.shape().polygon.transformed(it.trans()))
                    it.next()
            reg = reg.merged()
            ids = []
            for po in reg.each():
                ids.append(len(self.uf))
                self.uf.append(len(self.uf))
                self.regions.setdefault(sem, []).append((ids[-1], pya.Region(po)))
        for cut, la, lb in ((MCON, LI1, MET1), (VIA1, MET1, MET2),
                            (VIA2, MET2, MET3), (VIA3, MET3, MET4)):
            for i, po in self.regions.get(cut, []):
                for j, pa in self.regions.get(la, []):
                    if not (po & pa).is_empty():
                        self.union(i, j)
                for j, pb in self.regions.get(lb, []):
                    if not (po & pb).is_empty():
                        self.union(i, j)

    def comp_of_point(self, sem, x_um, y_um):
        x = int(x_um * 1000)
        y = int(y_um * 1000)
        p = pya.Region(pya.Box(x, y, x + 1, y + 1))
        for i, po in self.regions.get(sem, []):
            if not (p & po).is_empty():
                return self.find(i)
        return None

    def comp_of_box(self, sem, box):
        r = pya.Region(box)
        for i, po in self.regions.get(sem, []):
            if not (r & po).is_empty():
                return self.find(i)
        return None


def rec_boxes(ly, top, sem):
    li = ly.find_layer(*sem)
    out = []
    if li is None:
        return out
    it = top.begin_shapes_rec(li)
    while not it.at_end():
        out.append(it.shape().box.transformed(it.trans()))
        it.next()
    return out


def top_drawn_region(ly, top, sem):
    li = ly.find_layer(*sem)
    reg = pya.Region()
    if li is not None:
        for s in top.shapes(li).each():
            reg.insert(s)
    return reg


def grow_pads(ly, top, cut_sem, metal_sem, min_enc, target, label):
    cuts = rec_boxes(ly, top, cut_sem)
    drawn = pya.Shapes()
    li_met = ly.find_layer(*metal_sem)
    for s in top.shapes(li_met).each():
        drawn.insert(s)
    drawn_reg = pya.Region(drawn)
    drawn_reg = drawn_reg.merged()

    shapes = top.shapes(li_met)
    fixed = skipped = 0
    for cbox in cuts:
        creg = pya.Region(cbox)
        touching = drawn_reg.interacting(creg)
        if touching.is_empty():
            skipped += 1
            continue
        bb = touching.bbox()
        encs = (cbox.left - bb.left, bb.right - cbox.right,
                cbox.bottom - bb.bottom, bb.top - cbox.top)
        if min(encs) >= min_enc - 1:
            continue
        need = [max(0, target - e) for e in encs]
        nb = pya.Box(bb.left - need[0], bb.bottom - need[2],
                     bb.right + need[1], bb.top + need[3])
        shapes.insert(nb)
        drawn_reg.insert(nb)
        drawn_reg = drawn_reg.merged()
        fixed += 1
    print(f"  [{label}] grew {fixed} pads, {skipped} cuts without drawn metal")
    return fixed


def parse_report(path):
    rules = {}
    cur = None
    for line in open(path):
        t = line.strip()
        if not t or t.startswith("COUNT"):
            continue
        if t[0].isdigit() or t[0] == '-':
            p = [round(float(v.replace('um', '')) * 1000) for v in t.split()]
            rules.setdefault(cur, []).append(p)
        else:
            cur = t
    return rules


def fix_from_report(ly, top, report, via2_margin=90, via1_margin=60):
    n2 = n1 = 0
    for rule, tiles in report.items():
        if "via2.4a" in rule:
            cuts = rec_boxes(ly, top, VIA2)
            n2 = _grow_flagged(ly, top, cuts, tiles, VIA2, MET2,
                               via2_margin, "via2.4a")
        elif "via.5a" in rule:
            cuts = rec_boxes(ly, top, VIA1)
            n1 = _grow_flagged(ly, top, cuts, tiles, VIA1, MET1,
                               via1_margin, "via.5a")
    return n2, n1


def _grow_flagged(ly, top, cuts, tiles, cut_sem, metal_sem, margin, label):
    li_met = ly.find_layer(*metal_sem)
    shapes = top.shapes(li_met)
    drawn = pya.Shapes()
    for s in top.shapes(li_met).each():
        drawn.insert(s)
    drawn_reg = pya.Region(drawn).merged()
    fixed = 0
    for tile in tiles:
        tx, ty = (tile[0] + tile[2]) // 2, (tile[1] + tile[3]) // 2
        best = None
        bd = 1 << 62
        for cb in cuts:
            d = abs((cb.left + cb.right) // 2 - tx) ** 2 + \
                abs((cb.bottom + cb.top) // 2 - ty) ** 2
            if d < bd:
                bd = d
                best = cb
        if best is None or bd > 4_000_000:
            print(f"  [{label}] no cut within 2um of tile {tile}")
            continue
        creg = pya.Region(best)
        touch = drawn_reg.interacting(creg)
        if touch.is_empty():
            print(f"  [{label}] cut {best.to_s()} has no drawn metal")
            continue
        bb = touch.bbox()
        want = pya.Box(best.left - margin, best.bottom - margin,
                       best.right + margin, best.top + margin)
        nb = pya.Box(min(bb.left, want.left), min(bb.bottom, want.bottom),
                     max(bb.right, want.right), max(bb.top, want.top))
        if nb == bb:
            continue
        shapes.insert(nb)
        drawn_reg.insert(nb)
        drawn_reg = drawn_reg.merged()
        fixed += 1
        print(f"  [{label}] grew pad for cut {best.to_s()}: "
              f"{bb.to_s()} -> {nb.to_s()}")
    return fixed


def mcon_pair_candidates(ly, top):
    boxes = rec_boxes(ly, top, MCON)
    drawn = set()
    li = ly.find_layer(*MCON)
    for s in top.shapes(li).each():
        if s.is_box():
            drawn.add((s.box.left, s.box.bottom, s.box.right, s.box.top))
    boxes.sort(key=lambda b: (b.bottom, b.left))
    g = FlatGraph(ly, top)
    g.build([LI1, MET1, MET2, MET3, MET4, MCON, VIA1, VIA2, VIA3])
    vp = g.comp_of_point(MET2, 7.0, 77.6)
    vg = g.comp_of_point(MET1, 14.0, 78.3)
    print(f"  net comps: VPWR={vp} VGND={vg}")
    del_cands = []
    pairs = []
    n = len(boxes)
    for i in range(n):
        a = boxes[i]
        for j in range(i + 1, n):
            b = boxes[j]
            if b.bottom - a.top > 190:
                break
            dx = max(0, max(a.left, b.left) - min(a.right, b.right))
            dy = max(0, max(a.bottom, b.bottom) - min(a.top, b.top))
            if dx == 0 and dy == 0:
                continue
            d = (dx * dx + dy * dy) ** 0.5
            if d >= 190:
                continue
            ca = g.comp_of_box(MCON, a)
            cb = g.comp_of_box(MCON, b)
            pairs.append((a, b, d, ca, cb))
            a_drawn = (a.left, a.bottom, a.right, a.top) in drawn
            b_drawn = (b.left, b.bottom, b.right, b.top) in drawn
            if ca is not None and ca == cb and ca not in (vp, vg):
                continue
            if ca is not None and ca == cb:
                if a_drawn and not b_drawn:
                    del_cands.append(a)
                elif b_drawn and not a_drawn:
                    del_cands.append(b)
    same = sum(1 for p in pairs if p[3] is not None and p[3] == p[4])
    diff = sum(1 for p in pairs if None not in (p[3], p[4]) and p[3] != p[4])
    print(f"  mcon pairs < 0.19um: {len(pairs)}  same-net: {same}  "
          f"diff-net: {diff}  unknown: {len(pairs) - same - diff}")
    print(f"  deletable drawn mcons (same-net redundant): {len(del_cands)}")
    return pairs, del_cands


def fix_mcon2(ly, top):
    pairs, del_cands = mcon_pair_candidates(ly, top)
    li = ly.find_layer(*MCON)
    shapes = top.shapes(li)
    to_del = {(b.left, b.bottom, b.right, b.top) for b in del_cands}
    removed = 0
    for s in list(shapes.each()):
        if s.is_box():
            k = (s.box.left, s.box.bottom, s.box.right, s.box.top)
            if k in to_del:
                shapes.erase(s)
                to_del.discard(k)
                removed += 1
    print(f"  [mcon2] removed {removed} redundant mcons "
          f"({len(to_del)} unmatched)")
    return removed


def main():
    args = sys.argv[1:]
    ly = pya.Layout()
    ly.read(SRC)
    cell = ly.top_cell()

    print(f"snapped shapes : {snap_all(ly, cell)}")
    print(f"renamed labels : {rename_ch_labels(ly, cell)}")

    if "--fix-via5a" in args:
        grow_pads(ly, cell, VIA1, MET1, 30, 45, "via5a")
    if "--fix-via24a" in args:
        grow_pads(ly, cell, VIA2, MET2, 50, 70, "via24a")
    if "--fix-mcon2" in args:
        fix_mcon2(ly, cell)
    if "--report-mcon" in args:
        mcon_pair_candidates(ly, cell)
    rpt = [a.split("=", 1)[1] for a in args if a.startswith("--fix-from-report")]
    if rpt:
        report = parse_report(rpt[0])
        n2, n1 = fix_from_report(ly, cell, report)
        print(f"  [report] via2.4a pads grown: {n2}, via.5a pads grown: {n1}")

    ly.write(DST)
    print("wrote", DST)


if __name__ == "__main__":
    main()
