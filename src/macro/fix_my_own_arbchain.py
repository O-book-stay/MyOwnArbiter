#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# fix_my_own_arbchain.py
#
# Final touch-up of the hand-drawn arbiter macro GDS:
#   1. snap the two off-grid shapes onto the 0.005 um grid
#   2. rename the 16 met2 "CH" labels to ch[0]..ch[15]
#      (ascending y == stage index, matching input [15:0] ch)
#
# Source : my_own_arbchain.gds  (kept untouched)
# Output : arbchain.gds         (what the tt flow consumes)
# ============================================================
import os
import klayout.db as pya

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "my_own_arbchain.gds")
DST = os.path.join(HERE, "arbchain.gds")
GRID = 5                      # DBU = 0.005 um at 1 nm dbu

def snap(v):
    return round(v / GRID) * GRID

def shape_points(s):
    if s.is_box():
        b = s.box
        return [(b.left, b.bottom), (b.right, b.top)]
    if s.is_polygon():
        return [(p.x, p.y) for p in s.polygon.each_point_hull()]
    return []

ly = pya.Layout()
ly.read(SRC)
cell = ly.top_cell()

# ---------- 1) snap off-grid shapes (boxes + polygons) ----------
snapped = 0
for li in list(ly.layer_indexes()):
    shapes = cell.shapes(li)
    for s in list(shapes.each()):
        if s.is_box():
            b = s.box
            if (b.left % GRID or b.bottom % GRID or
                    b.right % GRID or b.top % GRID):
                shapes.replace(
                    s, pya.Box(snap(b.left), snap(b.bottom),
                               snap(b.right), snap(b.top)))
                snapped += 1
        elif s.is_polygon():
            raw = [pya.Point(p.x, p.y) for p in s.polygon.each_point_hull()]
            if any(p.x % GRID or p.y % GRID for p in raw):
                pts = [pya.Point(snap(p.x), snap(p.y)) for p in raw]
                if len(set((p.x, p.y) for p in pts)) < 3:
                    continue                  # degenerate after snap: keep
                shapes.replace(s, pya.Polygon(pts))
                snapped += 1
print(f"snapped shapes : {snapped}")

# ---------- 2) rename CH labels -> ch[0..15] in ascending y ----------
lab = ly.layer(69, 5)
chans = [s for s in cell.shapes(lab).each()
         if s.is_text() and s.text.string == "CH"]
chans.sort(key=lambda s: s.text.trans.disp.y)
assert len(chans) == 16, f"expected 16 CH labels, got {len(chans)}"
for i, s in enumerate(chans):
    t = s.text
    t.string = f"ch[{i}]"
    s.text = t
print(f"renamed labels : {len(chans)} (ch[0]..ch[15])")

# ---------- 3) verify ----------
off = 0
for li in ly.layer_indexes():
    for s in cell.shapes(li).each():
        for (x, y) in shape_points(s):
            if x % GRID or y % GRID:
                off += 1
print(f"offgrid points : {off}")
labels = sorted((s.text.string, s.text.trans.disp.y)
                for s in cell.shapes(lab).each() if s.is_text())
print("labels:")
for name, y in labels:
    print(f"   {name:<6} y={y * 0.001:.3f} um")
other = [n for n, _ in labels if not n.startswith("ch[")]
print(f"non-ch labels  : {other}")

ly.write(DST)
print("wrote", DST)