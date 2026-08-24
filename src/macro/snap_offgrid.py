#!/usr/bin/env python3
"""Snap all coordinates in arbchain.gds to the 0.005um (5nm) DRC grid."""

import pya

SRC = "arbchain.gds"
DST = "arbchain_snapped.gds"
GRID_UM = 0.005

layout = pya.Layout()
layout.read(SRC)
dbu = layout.dbu
grid_dbu = GRID_UM / dbu

def snap(v):
    return int(v / grid_dbu + 0.5) * grid_dbu

snapped_shapes = 0
snapped_insts = 0
kept = 0

for cell in layout.each_cell():
    for li in layout.layer_indexes():
        shapes = cell.shapes(li)
        for shape in list(shapes.each()):
            if shape.is_box():
                b = shape.box
                x1, y1 = snap(b.p1.x), snap(b.p1.y)
                x2, y2 = snap(b.p2.x), snap(b.p2.y)
                if x1 == x2 or y1 == y2:
                    kept += 1
                    continue
                shapes.replace(shape, pya.Box(x1, y1, x2, y2))
                snapped_shapes += 1
            elif shape.is_polygon():
                poly = shape.polygon
                pts = [pya.Point(snap(p.x), snap(p.y)) for p in poly.each_point_hull()]
                if len(set((p.x, p.y) for p in pts)) < 3:
                    kept += 1
                    continue
                shapes.replace(shape, pya.Polygon(pts))
                snapped_shapes += 1
            elif shape.is_path():
                path = shape.path
                pts = [pya.Point(snap(p.x), snap(p.y)) for p in path.each_point()]
                w = snap(path.width)
                if w < 1:
                    w = 1
                shapes.replace(shape, pya.Path(pts, w))
                snapped_shapes += 1
            elif shape.is_text():
                pass

    for inst in list(cell.each_inst()):
        tr = inst.trans
        if tr.disp.x % grid_dbu == 0 and tr.disp.y % grid_dbu == 0:
            continue
        ntr = pya.Trans(tr.rot, tr.is_mirror(), pya.Vector(snap(tr.disp.x), snap(tr.disp.y)))
        cia = inst.cell_inst
        if inst.is_regular_array():
            ncia = pya.CellInstArray(cia.cell, ntr,
                                     pya.Vector(snap(cia.ia.x), snap(cia.ia.y)),
                                     pya.Vector(snap(cia.ib.x), snap(cia.ib.y)),
                                     cia.na, cia.nb)
        else:
            ncia = pya.CellInstArray(cia.cell, ntr)
        cell.replace(inst, ncia)
        snapped_insts += 1

layout.write(DST)

layout2 = pya.Layout()
layout2.read(DST)
off = 0
for cell in layout2.each_cell():
    for li in layout2.layer_indexes():
        for shape in cell.shapes(li).each():
            poly = shape.polygon
            if poly is None:
                continue
            for p in poly.each_point_hull():
                if p.x % grid_dbu != 0 or p.y % grid_dbu != 0:
                    off += 1
                    break

print(f"DBU = {dbu} um, grid = {GRID_UM} um ({grid_dbu} DBU)")
print(f"shapes snapped: {snapped_shapes}, degenerate kept: {kept}")
print(f"instances snapped: {snapped_insts}")
print(f"off-grid points remaining in {DST}: {off}")
print(f"output: {DST}")
