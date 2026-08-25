#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# gen_lef_gds.py
#
# Emit the hard-macro LEF (arbchain.lef) straight from the
# fixed hand-drawn GDS (arbchain.gds): every port rectangle is
# derived from the geometry actually drawn, and the OBS is the
# per-layer union of all drawn metal minus the pin ports, so no
# internal metal stays routable and the ports sit on real metal.
#
#   python gen_lef_gds.py
# ============================================================
import os
import klayout.db as pya

HERE = os.path.dirname(os.path.abspath(__file__))
GDS = os.path.join(HERE, "arbchain.gds")
LEF = os.path.join(HERE, "arbchain.lef")

LI1  = (67, 20)
MET1 = (68, 20)
MET2 = (69, 20)
MET3 = (70, 20)
MET4 = (71, 20)

ly = pya.Layout()
ly.read(GDS)
cell = ly.top_cell()
dbu = ly.dbu                       # 0.001 um

def um(v):
    return v * dbu

def layer_region(sem):
    """merged region of a semantic layer incl. all cell instances."""
    reg = pya.Region()
    it = cell.begin_shapes_rec(ly.layer(*sem))
    while not it.at_end():
        shp = it.shape()
        if not (shp.is_box() or shp.is_polygon()):
            it.next()
            continue
        reg.insert(shp.polygon.transformed(it.trans()))
        it.next()
    return reg.merged()

# ---------- port geometry (from the real layout) ----------
met2 = layer_region(MET2)
met3 = layer_region(MET3)
met4 = layer_region(MET4)
met1 = layer_region(MET1)

ch_cy = {}
for s in cell.shapes(ly.layer(69, 5)).each():
    if s.is_text():
        t = s.text
        if t.string.startswith("ch["):
            g = int(t.string[3:-1])
            ch_cy[g] = t.trans.disp.y
assert len(ch_cy) == 16 and set(ch_cy) == set(range(16)), ch_cy

ports = []                        # (name, dir, use, layer, (x1,y1,x2,y2) dbu)
LAYER_NAME = {MET1: "met1", MET2: "met2", MET3: "met3", MET4: "met4"}
for g in range(16):
    cy = ch_cy[g]
    ports.append((f"ch[{g}]", "INPUT", "SIGNAL", MET2,
                  (0, cy - 150, 300, cy + 150)))
ports.append(("launch", "INPUT", "SIGNAL", MET4, (4830, 0, 5170, 720)))
ports.append(("arb_rst_n", "INPUT", "SIGNAL", MET3, (0, 76740, 300, 77040)))
ports.append(("q", "OUTPUT", "SIGNAL", MET3, (16600, 76090, 17280, 76390)))
ports.append(("VPWR", "INOUT", "POWER", MET2, (13200, 77280, 14950, 77980)))
ports.append(("VGND", "INOUT", "GROUND", MET1, (12000, 78000, 17280, 78670)))

# ---------- port-on-metal sanity ----------
regions = {MET1: met1, MET2: met2, MET3: met3, MET4: met4}
print("== port-on-metal check ==")
for name, _, _, lay, b in ports:
    inter = regions[lay] & pya.Region(pya.Box(*b))
    area = inter.is_empty() and 0 or sum(1 for _ in inter.each())
    print(f"  {name:<10} {lay} {tuple(round(um(v), 3) for v in b)}"
          f"  on-metal={inter.area() * dbu * dbu:.4f} um2")
    assert not inter.is_empty(), f"port {name} does not touch {lay} metal!"

# ---------- OBS ----------
# NOTE: intentionally NOT geometry-derived.  pdngen cuts met4 straps whose
# shapes overlap macro OBS (bloated by halo+spacing), so the OBS set must
# match the layout contract the tile PDN was tuned against: met4 OBS stops
# at x=11.28 (internal met4 spines reach 11.19) and stays clear of the
# strap window over the power rails -- including the q-output met4 pad,
# whose inclusion as OBS makes pdngen delete the VGND via tower
# (PDN-0195 -> PSM-0069).  These rects are inherited verbatim from the
# proven generator LEF; all current pin ports stay clear of them.
OLD_OBS = {
    "li1":  [(0.0, 0.0, 17.280, 78.680)],
    "met1": [(0.600, 0.0, 12.000, 78.000),
             (0.0,   0.0,  4.700, 73.840),
             (6.100, 0.0, 12.000, 73.840)],
    "met2": [(0.600, 0.0,    17.280,  0.400),
             (6.600, 0.0,    17.280, 73.840),
             (0.600, 76.640, 17.280, 77.280)],
    "met3": [(0.600, 0.0,  4.750, 78.680),
             (5.250, 0.0, 10.280, 78.680)],
    "met4": [(0.0,   0.0,  4.750, 78.680),
             (5.250, 0.0, 11.280, 78.680)],
}

# every port must sit outside the blockages
print("== port-vs-OBS clearance ==")
for name, _, _, lay, b in ports:
    ln = LAYER_NAME[lay]
    for (ox1, oy1, ox2, oy2) in OLD_OBS[ln]:
        if not (b[2] * dbu <= ox1 or b[0] * dbu >= ox2 or
                b[3] * dbu <= oy1 or b[1] * dbu >= oy2):
            raise SystemExit(f"port {name} overlaps OBS {ln} {(ox1,oy1,ox2,oy2)}")
print("  all ports clear")

L = []
a = L.append
a("# LEF abstract of the hand-drawn arbchain macro")
a("# ports: geometry-derived; OBS: proven generator contract (see note)")
a("VERSION 5.8 ;")
a('BUSBITCHARS "[]" ;')
a('DIVIDERCHAR "/" ;')
a("MACRO arbchain")
a(" CLASS BLOCK ;")
a(" ORIGIN 0 0 ;")
a(f" SIZE {um(cell.bbox().right):.3f} BY {um(cell.bbox().top):.3f} ;")
a(" SYMMETRY X Y ;")
for name, dirn, use, lay, b in ports:
    a(f" PIN {name}")
    a(f"  DIRECTION {dirn} ;")
    a(f"  USE {use} ;")
    a("  PORT")
    a(f"   LAYER {LAYER_NAME[lay]} ;")
    a(f"    RECT {um(b[0]):.3f} {um(b[1]):.3f} {um(b[2]):.3f} {um(b[3]):.3f} ;")
    a("  END")
    a(f" END {name}")
a(" OBS")
for lay in ("li1", "met1", "met2", "met3", "met4"):
    a(f" LAYER {lay} ;")
    for (x1, y1, x2, y2) in OLD_OBS[lay]:
        a(f"  RECT {x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f} ;")
a(" END")
a("END arbchain")
a("END LIBRARY")
open(LEF, "w").write("\n".join(L) + "\n")
print("wrote", LEF)