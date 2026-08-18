#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# gen_arbchain.py
#
# Generates the "arbchain" symmetric hard macro for the
# arbiter PUF switch chain (STAGES stages of two mux2_1 + one
# dlrtp_1 D-latch arbiter).
#
# Symmetry is guaranteed by construction:
#   * every stage is a mirror-symmetric pair of sky130 mux2_1
#   * the two delay-line nets (top/bot) are routed with
#     mirror-identical geometry about the macro centerline
#   * the challenge bit of each stage drives both muxes through
#     the same horizontal conductor
#
# Outputs (into the same directory as this script):
#   arbchain.gds   macro layout (streamed GDSII)
#   arbchain.lef   macro abstract (boundary + pins, hand written)
#   arbchain.vh    black-box header used by LibreLane synthesis
#   arbchain.nl.v  gate-level netlist of the macro (STA + GL sim)
#   arbchain.v     behavioural model for RTL simulation
#
# Cell data: the two standard cells are read from GDS/LEF files
# whose paths can be given on the command line.  If omitted the
# script looks under $PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/.
#
# Requires: python3 + klayout (pip install klayout)
# ============================================================

import argparse
import os
import re
import sys
import urllib.request

import klayout.db as pya


# pinned cell sources (google/skywater-pdk-libs-sky130_fd_sc_hd) used when
# the PDK is not installed locally (e.g. CI regeneration of the macro)
CELL_FILES = {
    "sky130_fd_sc_hd__mux2_1.gds": "cells/mux2/sky130_fd_sc_hd__mux2_1.gds",
    "sky130_fd_sc_hd__mux2_1.lef": "cells/mux2/sky130_fd_sc_hd__mux2_1.lef",
    "sky130_fd_sc_hd__dlrtp_1.gds": "cells/dlrtp/sky130_fd_sc_hd__dlrtp_1.gds",
    "sky130_fd_sc_hd__dlrtp_1.lef": "cells/dlrtp/sky130_fd_sc_hd__dlrtp_1.lef",
}
CELL_BASE = ("https://raw.githubusercontent.com/google/"
             "skywater-pdk-libs-sky130_fd_sc_hd/main/")


def ensure_cells(gds_dir, lef_dir):
    """Return (gds_dir, lef_dir) that actually contain the cells, fetching
    them from the pinned skywater-pdk-libs repo if not found locally."""
    import shutil
    import subprocess
    import tempfile
    for d in (gds_dir, lef_dir):
        if d and os.path.exists(os.path.join(d, "sky130_fd_sc_hd__mux2_1.gds")):
            return gds_dir, lef_dir
    tmp = tempfile.mkdtemp(prefix="arbchain_cells_")
    for fname, path in CELL_FILES.items():
        url = CELL_BASE + path
        dst = os.path.join(tmp, fname)
        print(f"fetching {url} -> {dst}")
        try:
            if shutil.which("curl"):
                subprocess.check_call(["curl", "-fsSL", "-o", dst, url],
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
            else:
                urllib.request.urlretrieve(url, dst)
        except Exception as e:
            sys.exit(f"failed to fetch {url}: {e}")
    return tmp, tmp


class _UF:
    def __init__(self):
        self.nodes = []

    def find(self, x):
        while self.nodes[x] != x:
            self.nodes[x] = self.nodes[self.nodes[x]]
            x = self.nodes[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.nodes[rb] = ra

# ------------------------------------------------------------------
# Parameters
# ------------------------------------------------------------------
# All rows are R0 (no R0/R180 alternation): this keeps every pin in
# the low part of the cell where it can be accessed below the met3
# VDD strap.  The row pitch is a whole multiple of the met3 routing
# track pitch (0.68um) so the ch[] signal pins land exactly on the
# met3 track grid (DRT pin access); 24 stages keep the macro inside
# the 1x1 core (H = 25*3.40 + 0.48 = 85.48 < 107.72 available).
STAGES = 24
MUX_W = 4.14          # mux2_1 width  (um)
MUX_H = 2.72          # cell height   (um)
LATCH_W = 5.98        # dlrtp_1 width
LATCH_H = 2.72
PITCH = 3.40          # row pitch = 5 * met3 track pitch (0.68)
GAP = 1.5             # half width of the central channel
CH = 2 * GAP          # channel width
W = 2 * (GAP + MUX_W)  # macro width
XC = W / 2            # centerline
YOFF = 0.24           # shift so the bottom VSS rail sits at y=0
H = (STAGES + 1) * PITCH + 2 * YOFF  # macro height

# LEF pin table (parsed from the cell LEF files)
MUX_LEF = "sky130_fd_sc_hd__mux2_1"
LATCH_LEF = "sky130_fd_sc_hd__dlrtp_1"

# GDS layer / datatype for sky130
# GDS layer / datatype for sky130  (values per libs.tech/klayout/tech/sky130A.map)
LAY_LI1  = (67, 20)
LAY_MET1 = (68, 20)
LAY_MET2 = (69, 20)
LAY_MET3 = (70, 20)
LAY_MET4 = (71, 20)
LAY_VIA  = (67, 44)   # mcon  li1-met1
LAY_VIA2 = (68, 44)   # via   met1-met2
LAY_VIA3 = (69, 44)   # via2  met2-met3
LAY_VIA4 = (70, 44)   # via3  met3-met4
LAY_PR   = (236, 0)   # prBoundary   ← 补回

# routing tracks (offset within a row, from the row origin y_g)
# all rows are R0 so the pin layout is identical every row:
#  - a0   : A0 pins          -> met4
#  - x    : X pins (sources) -> met4
#  - a1t  : A1 pins fed from bot spine -> met3
#  - a1b  : A1 pins fed from top spine -> met3
#  - ch   : S pins           -> met3 (on the met3 track grid: YOFF + ch
#           = 1.30 = 0.34 + 0.68*7 - 3.80, i.e. an exact met3 track)
EV = {"a0": 0.8, "a1t": 0.40, "a1b": 0.74, "x": 1.26, "ch": 1.06}
OD = {"a0": 0.8, "a1t": 0.40, "a1b": 0.74, "x": 1.26, "ch": 1.06}

# power straps (vertical met3 in the channel)
STRAPS = {
    "VSS_L": 4.70,
    "VDD_L": 5.10,
    "VDD_R": 6.48,
    "VSS_R": 6.88,
}

# spines (vertical met4 in the channel), two pairs alternated per
# stage so consecutive nets never share a vertical conductor
PAIR_A = (5.34, 5.94)
PAIR_B = (4.94, 6.34)

# ------------------------------------------------------------------
# Power corridor (right of the channel)
# ------------------------------------------------------------------
# The macro is powered through two horizontal met2 rails drawn in the
# free band above the latch row (latch top = lat+2.96, macro top = H).
# The tile-level PDN met4 straps run vertically at their NOMINAL
# positions and cross the rails in the corridor; pdngen then builds
# via3+via4 towers at the crossings (PDN_CFG macro connect met2<->met4).
#
# IMPORTANT: pdngen bloats each macro OBS by the PDN halo plus the layer
# spacing and CUTS any strap whose own obstruction overlaps that region
# (Straps::cutShapes).  RepairChannelStraps only re-routes a cut strap
# when it leaves a DISCONNECTED channel; here the strap pieces and the
# followpins stay connected via the other straps, so no channel exists
# and the cut strap is left as-is (the PSM-0039 failure mechanism).
# Therefore the macro must be placed so that NO strap obstruction
# overlaps its OBS + halo + spacing.  Strap grid (sky130A 1x1 tile,
# FP_PDN_VPITCH 38.87 / PDN_VOFFSET 16.32 from the core origin
# x=2.76, width 1.6, spacing 1.7, starts_with POWER):
#   VPWR: 19.08, 57.95, 96.82, 135.69   VGND: 22.38, 61.25, 100.12, 138.99
# With MACRO_X below (83.30) + PDN_HORIZONTAL_HALO 0.3 (config.json),
# the channel (0..W) sits in the gap between pair 2 (ends 62.05) and
# pair 3 (starts 96.02): the met4 OBS+halo+spacing edge lands at 94.88,
# 0.84um clear of the VPWR strap obstruction at 95.72, and the corridor
# (W..TW) covers pair 3 so both straps cross the met2/met1 rails.
MACRO_X = 83.30                          # macro origin x in the tile
MACRO_Y = 7.20                           # macro origin y in the tile (config.json)
CORR_W = 6.00                             # corridor width
TW = W + CORR_W                           # total macro width
# power rails in the top free band (latch top = lat+2.96, macro top = H):
# a thin 0.17um rail cannot host the via3/via4 tower cuts, so VPWR gets
# one thick met2 rail and VGND uses a met1 rail that overlaps the VSS_R
# met1 strap; the VPWR rail must stop short of the VGND tower x-range
# VP_RAIL is >= 0.67um tall so pdngen can fit its 1.6x0.67um met2->met4
# via tower (0.60um failed: no tower -> RepairChannelStraps cut the strap
# -> VPWR unconnected, PSM-0069 / 152 PDN violations).
VP_RAIL = (H - 0.70, H)                  # VPWR met2 rail y-extent (103.38..103.98)
VP_RAIL_X = 14.95                        # VPWR rail right end (clear of VG tower)
VG_RAIL = (H - 0.68, H - 0.01)           # VGND met1 rail y-extent (103.30..103.97)
VG_RAIL_X0 = STRAPS["VSS_R"] - 0.09      # overlap the VSS_R met1 strap

# met3 VDD strap of the mux/latch cells occupies y1.355..2.91, so all
# pin via-stacks stay below it (access band 0.24 .. 1.34 um)
ACCESS_MAX = 1.34

VIA = 0.170           # via size
M2W = 0.170           # wire width


def pt(x, y):
    return (round(x * 1000), round(y * 1000))


class Cell:
    """A standard cell: pins (name -> li1 rects, um coords), bbox, GDS ref."""

    def __init__(self, name, gds_path, lef_path):
        self.name = name
        self.gds_path = gds_path
        self.lef_path = lef_path
        self.pins = {}       # name -> list of (layer,(x1,y1,x2,y2)) um
        self._parse_lef()
        self._load_gds()

    def _parse_lef(self):
        cur = None
        self.size = (0.0, 0.0)
        with open(self.lef_path) as fh:
            for line in fh:
                if re.match(r"\s*(OBS|END)\b", line):
                    cur = None
                    continue
                m = re.search(r"MACRO\s+(\S+)", line)
                if m:
                    cur = None
                m = re.search(r"PIN\s+(\S+)", line)
                if m:
                    cur = m.group(1)
                    self.pins.setdefault(cur, [])
                m = re.search(r"LAYER\s+(\S+)\s*;", line)
                if m and cur:
                    self._layer = m.group(1)
                m = re.match(r"\s*SIZE\s+([\d.\-]+)\s+BY\s+([\d.\-]+)\s*;", line)
                if m:
                    self.size = (float(m.group(1)), float(m.group(2)))
                m = re.match(r"\s*RECT\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*;", line)
                if m and cur:
                    x1, y1, x2, y2 = (float(m.group(i)) for i in range(1, 5))
                    self.pins[cur].append((self._layer, (x1, y1, x2, y2)))

    def _load_gds(self):
        self.ly = pya.Layout()
        self.ly.read(self.gds_path)
        self.cell = self.ly.cell(self.name)
        if self.cell is None:
            sys.exit(f"cell {self.name} not found in {self.gds_path}")
        self.dbu = self.ly.dbu
        # layers used by this cell (for connectivity)
        self._layer_map = {}
        for ln in self.ly.layer_infos():
            self._layer_map[(ln.layer, ln.datatype)] = self.ly.layer(ln.layer, ln.datatype)
        self._build_pin_metal()

    def _region(self, ln, dt):
        r = pya.Region()
        it = self.cell.begin_shapes_rec(self.ly.layer(ln, dt))
        while not it.at_end():
            r.insert(it.shape().bbox().transformed(it.trans()))
            it.next()
        return r.merged()

    def _build_pin_metal(self):
        """Attribute the cell's metal geometry to each pin via
        via-based connectivity, so pin access can avoid other nets."""
        metals = {
            "li1":  self._region(67, 20),
            "met1": self._region(68, 20),
            "met2": self._region(69, 20),
            "met3": self._region(70, 20),
            }
        cuts = {
            "via":  self._region(67, 44),
            "via2": self._region(68, 44),
            "via3": self._region(69, 44)}

        polys = {}
        uf = _UF()
        nid = 0
        for name, reg in metals.items():
            polys[name] = []
            for po in reg.each():
                polys[name].append((nid, po))
                uf.nodes.append(nid)
                nid += 1
        for (cn, la, lb) in [("via", "li1", "met1"), ("via2", "met1", "met2"),
                             ("via3", "met2", "met3")]:
            for cp in cuts[cn].each():
                ids = []
                creg = pya.Region(cp)
                for (i, p) in polys[la]:
                    if not (pya.Region(p) & creg).is_empty():
                        ids.append(i)
                for (i, p) in polys[lb]:
                    if not (pya.Region(p) & creg).is_empty():
                        ids.append(i)
                if ids:
                    for i in ids[1:]:
                        uf.union(ids[0], i)
        self.pin_metal = {}
        for pin in self.pins:
            comps = set()
            for (layer, r) in self.pins[pin]:
                if layer != "li1":
                    continue
                cx = int(((r[0] + r[2]) / 2) / self.dbu)
                cy = int(((r[1] + r[3]) / 2) / self.dbu)
                p = pya.Point(cx, cy)
                for (i, po) in polys["li1"]:
                    if po.inside(p):
                        comps.add(uf.find(i))
                        break
            reg = pya.Region()
            for name in metals:
                for (i, po) in polys[name]:
                    if uf.find(i) in comps:
                        reg.insert(po)
            reg.merge()
            self.pin_metal[pin] = reg

    def other_pin_metal(self, pin):
        reg = pya.Region()
        for p, r in self.pin_metal.items():
            if p != pin:
                reg += r
        return reg.merged()

    def bbox_um(self):
        b = self.cell.bbox()
        return (b.left * self.dbu, b.bottom * self.dbu, b.right * self.dbu, b.top * self.dbu)


# ------------------------------------------------------------------
# Geometry helpers (all coords in um floats)
# ------------------------------------------------------------------
class Draw:
    def __init__(self, ly, top):
        self.ly = ly
        self.top = top
        self.layers = {}
        self.shapes = []   # (layer, (x1,y1,x2,y2)) in um

    def l(self, layer):
        if layer not in self.layers:
            self.layers[layer] = self.ly.layer(layer[0], layer[1])
        return self.layers[layer]

    def box(self, layer, x1, y1, x2, y2):
        self.top.shapes(self.l(layer)).insert(
            pya.Box(pt(x1, y1)[0], pt(x1, y1)[1], pt(x2, y2)[0], pt(x2, y2)[1])
        )
        self.shapes.append((layer, (x1, y1, x2, y2)))

    def h(self, layer, y, x0, x1, w=M2W):
        self.box(layer, x0, y - w / 2, x1, y + w / 2)

    def v(self, layer, x, y0, y1, w=M2W):
        self.box(layer, x - w / 2, y0, x + w / 2, y1)


def row_tracks(g):
    return EV if g % 2 == 0 else OD


# met4 routing tracks (vertical) are at global X = MET4_YOFF + MET4_YPITCH*n
MET4_YOFF, MET4_YPITCH = 0.46, 0.92
# met3 routing tracks (horizontal) are at global Y = MET3_XOFF + MET3_XPITCH*n
MET3_XOFF, MET3_XPITCH = 0.34, 0.68


def snap_met3_y(y_local):
    """Snap a macro-local Y to the nearest met3 routing track."""
    g = MACRO_Y + y_local
    return MET3_XOFF + MET3_XPITCH * round((g - MET3_XOFF) / MET3_XPITCH) - MACRO_Y


def snap_met4_x(x_local):
    """Snap a macro-local X to the nearest met4 routing track."""
    g = MACRO_X + x_local
    return MET4_YOFF + MET4_YPITCH * round((g - MET4_YOFF) / MET4_YPITCH) - MACRO_X


# ------------------------------------------------------------------
# Transform construction
# ------------------------------------------------------------------
def top_trans(g):
    y = g * PITCH + YOFF
    return pya.Trans(0, False, 0, round(y * 1000))


def bot_trans(g):
    y = g * PITCH + YOFF
    # mirror of the R0 top about the centerline x = Xc (x -> -x, +W)
    return pya.Trans(0, False, round(W * 1000), round(y * 1000)) * pya.Trans.M90


def latch_trans(y):
    x0 = (W - LATCH_W) / 2
    return pya.Trans(0, False, round(x0 * 1000), round(y * 1000))


def pin_rects_um(cell, trans, pin):
    """Return the pin rects (um, macro coords) for a placed instance."""
    out = []
    dbu = cell.dbu
    for _, r in cell.pins.get(pin, []):
        b = pya.Box(round(r[0] / dbu), round(r[1] / dbu),
                    round(r[2] / dbu), round(r[3] / dbu))
        b = b.transformed(trans)
        out.append((b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu))
    return out


def pin_rects_um_layer(cell, trans, pin):
    """Return (layer_name, rect) pairs for a placed instance pin."""
    out = []
    dbu = cell.dbu
    for layer, r in cell.pins.get(pin, []):
        b = pya.Box(round(r[0] / dbu), round(r[1] / dbu),
                    round(r[2] / dbu), round(r[3] / dbu))
        b = b.transformed(trans)
        out.append((layer, (b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu)))
    return out


def pin_center(cell, trans, pin, y):
    """Access point on a pin: the (x,y) of a met2 track that lies on the
    pin (assumes a horizontal met2 track at height y)."""
    best = None
    for r in pin_rects_um(cell, trans, pin):
        if r[1] <= y <= r[3] and r[2] - r[0] >= VIA - 0.001:
            # met1 pad must fit vertically inside the pin rect
            if r[1] <= y - VIA / 2 and y + VIA / 2 <= r[3]:
                cx = max(r[0] + VIA / 2, min(r[2] - VIA / 2, XC))
                return cx
            best = (r, cx) if best is None else best
    if best is not None:
        r, cx = best
        return cx
    return None


def safe_access(cell, trans, pin, y_track):
    """Find a via-stack access point (x, y) on `pin` of a placed cell
    that is below the met3 VDD strap (which sits at local y>1.355 of
    the cell).  y_track is the desired routing height in *global*
    coordinates; the access is placed on the intended track whenever
    the pin fully contains it (so tracks stay distinct), and falls
    back to a partial overlap for pins that start above the strap."""
    # cell's local-frame origin (local y=0) in global coordinates
    body = pya.Box(0, 0, int(cell.size[0] / cell.dbu), int(cell.size[1] / cell.dbu))
    tb = body.transformed(trans)
    cell_bottom = tb.bottom * cell.dbu
    acc_max = cell_bottom + ACCESS_MAX
    rects = pin_rects_um(cell, trans, pin)
    rects = [r for r in rects if r[2] - r[0] >= VIA - 0.001]
    # 1) full containment on the requested track
    for r in rects:
        y_lo = r[1] + VIA / 2 + 0.02
        y_hi = min(r[3] - VIA / 2 - 0.02, acc_max)
        if y_lo <= y_track <= y_hi:
            x = (r[0] + r[2]) / 2
            x = max(r[0] + VIA / 2, min(r[2] - VIA / 2, x))
            return (x, y_track)
    # 2) partial overlap (pad overlaps li1, met3 pad stays below strap)
    for r in rects:
        y_lo = r[1] - VIA / 2 + 0.03
        y_hi = min(r[3], acc_max - VIA / 2 - 0.01)
        if y_hi < y_lo:
            continue
        y = max(y_lo, min(y_track, y_hi))
        if not (y + VIA / 2 >= r[1] - 0.005 and y - VIA / 2 <= r[3] + 0.005):
            continue
        x = (r[0] + r[2]) / 2
        x = max(r[0] + VIA / 2, min(r[2] - VIA / 2, x))
        return (x, y)
    return None


def access(cell, trans, pin, y_track):
    """safe_access returning just x (for callers that only need x)."""
    p = safe_access(cell, trans, pin, y_track)
    if p is None:
        return None
    return p[0]


# ------------------------------------------------------------------
# Main generator
# ------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell-gds-dir", help="dir containing cell gds files")
    ap.add_argument("--cell-lef-dir", help="dir containing cell lef files")
    ap.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()

    def default_dir(sub):
        pdk = os.environ.get("PDK_ROOT", "")
        return os.path.join(pdk, "sky130A", "libs.ref", "sky130_fd_sc_hd", sub)

    gds_dir = args.cell_gds_dir or default_dir("gds")
    lef_dir = args.cell_lef_dir or default_dir("lef")
    gds_dir, lef_dir = ensure_cells(gds_dir, lef_dir)

    mux = Cell(MUX_LEF, os.path.join(gds_dir, "sky130_fd_sc_hd__mux2_1.gds"),
               os.path.join(lef_dir, "sky130_fd_sc_hd__mux2_1.lef"))
    latch = Cell(LATCH_LEF, os.path.join(gds_dir, "sky130_fd_sc_hd__dlrtp_1.gds"),
                 os.path.join(lef_dir, "sky130_fd_sc_hd__dlrtp_1.lef"))

    print(f"mux cell {mux.name}  bbox {mux.bbox_um()}")
    print(f"latch cell {latch.name}  bbox {latch.bbox_um()}")
    for p in mux.pins:
        print("  mux pin", p)
    for p in latch.pins:
        print("  latch pin", p)

    # ----------------------------------------------------------
    # Build the layout
    # ----------------------------------------------------------
    ly = pya.Layout()
    ly.dbu = 0.001
    macro = ly.create_cell("arbchain")
    d = Draw(ly, macro)

    ly.read(mux.gds_path)
    ly.read(latch.gds_path)
    mux_ref = ly.cell(mux.name)
    latch_ref = ly.cell(latch.name)

    # --- instances ---
    for g in range(STAGES):
        y = g * PITCH
        macro.insert(pya.CellInstArray(mux_ref, top_trans(g)))
        macro.insert(pya.CellInstArray(mux_ref, bot_trans(g)))
    ly_r = STAGES * PITCH + YOFF
    macro.insert(pya.CellInstArray(latch_ref, latch_trans(ly_r)))

    # helper closures
    def viat(x, y):
        d.box(LAY_VIA, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)

    def via2(x, y):
        d.box(LAY_VIA2, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)

    def via3(x, y):
        d.box(LAY_VIA3, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)

    def via4(x, y):
        d.box(LAY_VIA4, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)

    def pad(layer, x, y):
        d.box(layer, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)

    def tap_m3(cell, trans, pin, y_track):
        """via-stack up to met3 (A0/A1/S pins). Returns (x,y) or None."""
        pt = safe_access(cell, trans, pin, y_track)
        if pt is None:
            return None
        x, y = pt
        viat(x, y)
        pad(LAY_MET1, x, y)
        via2(x, y)
        pad(LAY_MET2, x, y)
        via3(x, y)
        pad(LAY_MET3, x, y)
        return (x, y)

    def tap_m4(cell, trans, pin, y_track):
        """via-stack up to met4 (X pins, latch pins, launch). (x,y) or None."""
        pt = safe_access(cell, trans, pin, y_track)
        if pt is None:
            return None
        x, y = pt
        viat(x, y)
        pad(LAY_MET1, x, y)
        via2(x, y)
        pad(LAY_MET2, x, y)
        via3(x, y)
        pad(LAY_MET3, x, y)
        via4(x, y)
        pad(LAY_MET4, x, y)
        return (x, y)

    def tap_m3_pin(cell, trans, pin, y_track, to_y=None):
        """via-stack to an on-grid met3 pad (met2 jog from the cell pin).
        Used for the macro's met3 signal pins whose natural access lands
        off-grid (latch Q / RESET_B).  `to_y` forces a target track."""
        pt = safe_access(cell, trans, pin, y_track)
        if pt is None:
            return None
        x, y = pt
        ys = snap_met3_y(y) if to_y is None else to_y
        viat(x, y)
        pad(LAY_MET1, x, y)
        via2(x, y)
        pad(LAY_MET2, x, y)
        if abs(ys - y) > 0.0005:
            y0, y1 = (ys, y) if ys < y else (y, ys)
            d.v(LAY_MET2, x, y0, y1)
        via3(x, ys)
        pad(LAY_MET3, x, ys)
        return (x, ys)

    def spine(layer, x, y0, y1):
        if y1 < y0:
            y0, y1 = y1, y0
        d.v(layer, x, y0, y1)

    def hwire(layer, y, x0, x1):
        if x1 < x0:
            x0, x1 = x1, x0
        d.h(layer, y, x0, x1)

    # --- inter-stage nets (top[g], bot[g]) and ch[g] ---
    # ch[0] (stage 0 S pins -> left-edge met3 pin, on the met3 track)
    tc0 = row_tracks(0)
    yc0 = YOFF + tc0["ch"]
    s1 = tap_m3(mux, top_trans(0), "S", yc0)
    s2 = tap_m3(mux, bot_trans(0), "S", yc0)
    if s1 and s2:
        hwire(LAY_MET3, yc0, 0.0, s2[0])

    for g in range(1, STAGES):
        y_prev = (g - 1) * PITCH + YOFF
        y_cur = g * PITCH + YOFF
        tp = row_tracks(g - 1)
        tc = row_tracks(g)
        X_T, X_B = PAIR_A if g % 2 == 0 else PAIR_B

        # top[g]: X(top,g-1) -> A0(top,g) + A1(bot,g)
        src = tap_m4(mux, top_trans(g - 1), "X", y_prev + tp["x"])
        a0 = tap_m4(mux, top_trans(g), "A0", y_cur + tc["a0"])
        a1 = tap_m3(mux, bot_trans(g), "A1", y_cur + tc["a1b"])
        if src and a0 and a1:
            sxs, sysy = src
            a0x, a0y = a0
            a1x, a1y = a1
            hwire(LAY_MET4, sysy, sxs, X_T)
            spine(LAY_MET4, X_T, sysy, a0y)
            spine(LAY_MET4, X_T, sysy, a1y)
            hwire(LAY_MET4, a0y, a0x, X_T)
            hwire(LAY_MET3, a1y, X_T, a1x)
            via4(X_T, a1y)

        # bot[g]: X(bot,g-1) -> A1(top,g) + A0(bot,g)
        src = tap_m4(mux, bot_trans(g - 1), "X", y_prev + tp["x"])
        a1 = tap_m3(mux, top_trans(g), "A1", y_cur + tc["a1t"])
        a0 = tap_m4(mux, bot_trans(g), "A0", y_cur + tc["a0"])
        if src and a1 and a0:
            sxs, sysy = src
            a1x, a1y = a1
            a0x, a0y = a0
            hwire(LAY_MET4, sysy, X_B, sxs)
            spine(LAY_MET4, X_B, sysy, a1y)
            spine(LAY_MET4, X_B, sysy, a0y)
            hwire(LAY_MET3, a1y, a1x, X_B)
            via4(X_B, a1y)
            hwire(LAY_MET4, a0y, X_B, a0x)

        # ch[g]
        yc = y_cur + tc["ch"]
        s1 = tap_m3(mux, top_trans(g), "S", yc)
        s2 = tap_m3(mux, bot_trans(g), "S", yc)
        if s1 and s2:
            hwire(LAY_MET3, yc, 0.0, s2[0])

    # --- launch (feeds stage 0 both A inputs) ---
    tc0 = row_tracks(0)
    y0 = YOFF
    xc = snap_met4_x(XC)
    la0 = tap_m4(mux, top_trans(0), "A0", y0 + tc0["a0"])
    lb0 = tap_m4(mux, bot_trans(0), "A0", y0 + tc0["a0"])
    la1 = tap_m3(mux, top_trans(0), "A1", y0 + tc0["a1t"])
    lb1 = tap_m3(mux, bot_trans(0), "A1", y0 + tc0["a1b"])
    ys = []
    if la0 and lb0:
        hwire(LAY_MET4, la0[1], la0[0], xc)
        hwire(LAY_MET4, lb0[1], xc, lb0[0])
        ys.append(la0[1])
    if la1 and lb1:
        hwire(LAY_MET3, la1[1], la1[0], xc)
        via4(xc, la1[1])
        hwire(LAY_MET3, lb1[1], xc, lb1[0])
        via4(xc, lb1[1])
        ys.append(la1[1])
        ys.append(lb1[1])
    if ys:
        spine(LAY_MET4, xc, 0.15, max(ys))
        d.box(LAY_MET4, xc - 0.17 / 2, 0, xc + 0.17 / 2, 0.70)

    # --- latch connections ---
    ylat = ly_r
    tp = row_tracks(STAGES - 1)
    X_T, X_B = PAIR_A
    # top[STAGES]: X(top,STAGES-1) -> latch D  (latch-local y 1.2, met3)
    src = tap_m4(mux, top_trans(STAGES - 1), "X", ylat - PITCH + tp["x"])
    dpt = tap_m3(latch, latch_trans(ylat), "D", ylat + 1.2)
    if src and dpt:
        sxs, sysy = src
        dx, dy = dpt
        hwire(LAY_MET4, sysy, sxs, X_T)
        spine(LAY_MET4, X_T, sysy, dy)
        hwire(LAY_MET3, dy, dx, X_T)
        via4(X_T, dy)
    # bot[STAGES]: X(bot,STAGES-1) -> latch GATE  (latch-local y 1.0, met3)
    src = tap_m4(mux, bot_trans(STAGES - 1), "X", ylat - PITCH + tp["x"])
    gpt = tap_m3(latch, latch_trans(ylat), "GATE", ylat + 1.0)
    if src and gpt:
        sxs, sysy = src
        gx, gy = gpt
        hwire(LAY_MET4, sysy, X_B, sxs)
        spine(LAY_MET4, X_B, sysy, gy)
        hwire(LAY_MET3, gy, gx, X_B)
        via4(X_B, gy)
    # q: latch Q -> right edge of the macro (on the lower met3 track,
    # below D/GATE, clear of the corridor via towers)
    latch_track = snap_met3_y(ylat + 0.38)
    qpt = tap_m3_pin(latch, latch_trans(ylat), "Q", ylat + 0.6, to_y=latch_track)
    if qpt:
        hwire(LAY_MET3, qpt[1], qpt[0], TW)
    # arb_rst_n: left edge -> RESET_B  (same lower met3 track as q)
    rpt = tap_m3_pin(latch, latch_trans(ylat), "RESET_B", ylat + 0.4, to_y=latch_track)
    if rpt:
        hwire(LAY_MET3, rpt[1], 0, rpt[0])

    # --- power ---
    # vertical met1 straps in the channel (connect the met2 rails)
    for name, x in STRAPS.items():
        d.v(LAY_MET1, x, 0, H)

    def rail_bands(cell, tr, pin):
        """full-width met1 abutment rail bands of a placed cell."""
        out = set()
        for (layer, r) in pin_rects_um_layer(cell, tr, pin):
            if layer == "met1" and (r[2] - r[0]) >= MUX_W - 0.01:
                out.add((round(r[1], 3), round(r[3], 3)))
        return out

    # per-row cell rail bridges + via2 from met1 straps to met2 rails
    for g in range(STAGES):
        y = g * PITCH + YOFF
        t = top_trans(g)
        b = bot_trans(g)
        bands = {}  # net -> set of (y0,y1)
        for tr in (t, b):
            for net, pin in (("VDD", "VPWR"), ("VSS", "VGND")):
                bands.setdefault(net, set()).update(rail_bands(mux, tr, pin))
        for net, ys in bands.items():
            for (y0, y1) in ys:
                ym = (y0 + y1) / 2
                if ym <= y + MUX_H + 0.01:  # bottom/top band of this row
                    d.h(LAY_MET2, ym, 0, TW)
        for (tr, sx) in ((t, STRAPS["VDD_L"]), (t, STRAPS["VSS_L"]),
                         (b, STRAPS["VDD_R"]), (b, STRAPS["VSS_R"])):
            net = "VDD" if sx in (STRAPS["VDD_L"], STRAPS["VDD_R"]) else "VSS"
            pin = "VPWR" if net == "VDD" else "VGND"
            for (y0, y1) in rail_bands(mux, tr, pin):
                via2(sx, (y0 + y1) / 2)
    # latch power: connect met1 rails to the straps via via2
    ylat = STAGES * PITCH + YOFF
    for (pin, net) in (("VPWR", "VDD"), ("VGND", "VSS")):
        s1 = STRAPS["VDD_L"] if net == "VDD" else STRAPS["VSS_L"]
        for (y0, y1) in rail_bands(latch, latch_trans(ylat), pin):
            ym = (y0 + y1) / 2
            d.h(LAY_MET2, ym, s1, TW)
            via2(s1, ym)

    # --- top-band power rails: the tile PDN met4 straps cross them at
    # the corridor and pdngen builds the via towers ---
    d.box(LAY_MET2, 0, VP_RAIL[0], VP_RAIL_X, VP_RAIL[1])
    d.box(LAY_MET1, VG_RAIL_X0, VG_RAIL[0], TW, VG_RAIL[1])
    # tie the VPWR rail down to the full-height met1 VDD straps
    for sx in (STRAPS["VDD_L"], STRAPS["VDD_R"]):
        if sx < VP_RAIL_X:
            via2(sx, (VP_RAIL[0] + VP_RAIL[1]) / 2)

    # --- boundary ---
    d.box(LAY_PR, 0, 0, TW, H)

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    gds = os.path.join(out_dir, "arbchain.gds")
    ly.write(gds)
    print("wrote", gds)

    # dump the drawn routing for the checker (cells may be abstract views)
    import json
    with open(os.path.join(out_dir, "arbchain_routing.json"), "w") as fh:
        json.dump([{"layer": list(layer), "box": [round(v, 3) for v in box]}
                   for layer, box in d.shapes], fh)

    # text artifacts (LEF / black-box header / gate-level netlist / behavioural)
    emit_artifacts(out_dir)


# ------------------------------------------------------------------
# Text artifacts
# ------------------------------------------------------------------
def emit_artifacts(out_dir):
    name = "arbchain"
    lat = STAGES * PITCH + YOFF

    def ch_y(g):
        return g * PITCH + YOFF + EV["ch"]

    # ---- LEF ----
    def pin_rect(layer, x1, y1, x2, y2):
        return (layer, (x1, y1, x2, y2))

    lef_pins = []
    for g in range(STAGES):
        lef_pins.append(("ch[%d]" % g, "INPUT", "SIGNAL", [pin_rect("met3", 0.0, ch_y(g) - 0.15, 0.30, ch_y(g) + 0.15)]))
    xsp = snap_met4_x(XC)
    lef_pins.append(("launch", "INPUT", "SIGNAL", [pin_rect("met4", xsp - 0.15, 0.0, xsp + 0.15, 0.70)]))
    lef_pins.append(("arb_rst_n", "INPUT", "SIGNAL", [pin_rect("met3", 0.0, lat + 0.38 - 0.15, 0.30, lat + 0.38 + 0.15)]))
    lef_pins.append(("q", "OUTPUT", "SIGNAL", [pin_rect("met3", TW - 0.68, lat + 0.38 - 0.15, TW, lat + 0.38 + 0.15)]))
    # power pins: top-band rails, exposed only over the power corridor
    # (x = W..TW) so they do not intersect the channel's met3/met4
    # obstructions (PDN-0006); the tile-level PDN met4 straps cross them
    # there and pdngen builds the via towers (PDN_CFG macro connect
    # met2<->met4 / met1<->met4)
    lef_pins.append(("VPWR", "INOUT", "POWER",
                     [pin_rect("met2", W, VP_RAIL[0], TW, VP_RAIL[1])]))
    lef_pins.append(("VGND", "INOUT", "GROUND",
                     [pin_rect("met1", W, VG_RAIL[0], TW, VG_RAIL[1])]))

    lef = ["# LEF abstract of the arbchain macro (generated)",
           "VERSION 5.8 ;", "BUSBITCHARS \"[]\" ;", "DIVIDERCHAR \"/\" ;",
           "MACRO %s" % name,
           "  CLASS BLOCK ;", "  ORIGIN 0 0 ;",
           "  SIZE %.3f BY %.3f ;" % (TW, H),
           "  SYMMETRY X Y ;"]
    for pin, direction, use, rects in lef_pins:
        lef.append("  PIN %s" % pin)
        lef.append("    DIRECTION %s ;" % direction)
        lef.append("    USE %s ;" % use)
        for layer, r in rects:
            lef.append("    PORT")
            lef.append("      LAYER %s ;" % layer)
            lef.append("        RECT %.3f %.3f %.3f %.3f ;" % r)
            lef.append("    END")
        lef.append("  END %s" % pin)
    # OBS: block the router over the whole macro except the pin access
    # windows:
    #  - met3 left strip x=0..0.6 (ch[] / arb_rst_n pins), with met2 open
    #    below it so the DRT can drop a via2 (met2-met3) onto the pins;
#  - met3 launch window x=xsp-0.2..xsp+0.2 below y=0.75 (via3 to the
#    met4 launch stub, xsp = snap_met4_x(XC));
    #  - met3 right strip around q (x=16.98..17.28), met2 open below it;
    #  - met4 bottom strip (launch pin) y=0..0.6;
    #  - top band above the latch rail (power pins + pdngen towers) and
    #    the met3/met4 corridor (PDN straps pass through it).
    qy = lat + 0.38
    x_y = EV["x"] + YOFF  # X-tap via-stack y within each row
    # met1/met2 OBS top: just below the power pins (VGND met1, VPWR met2)
    met1_top = VG_RAIL[0]   # H - 0.68
    met2_top = VP_RAIL[0]   # H - 0.60
    # q pin access: expose a full-height met3 strip on the right edge
    # (x = q_x..TW) plus a tall met2/met1 window around qy, so the DRT can
    # reach the met3 q pin via via2 -> met2 -> via2 -> met3 (on a met3
    # track above/below qy) or via2 -> met2 -> via -> met1.
    q_x = TW - 0.90        # left edge of the q met3 strip
    q_hi = lat + 2.00      # met1/met2 window top (reaches the met3 track above qy)
    m1_vss = lat + 0.24    # latch VGND met1 rail top
    m2_vss = lat + 0.085   # latch VGND met2 rail top
    lef.append("  OBS")
    lef.append("    LAYER li1 ;")
    lef.append("      RECT 0 0 %.3f %.3f ;" % (TW, H))
    lef.append("    LAYER met1 ;")
    lef.append("      RECT 0 0 16.600 %.3f ;" % met1_top)
    lef.append("      RECT 16.600 0 %.3f %.3f ;" % (TW, m1_vss))
    lef.append("      RECT 16.600 %.3f %.3f %.3f ;" % (q_hi, TW, met1_top))
    lef.append("    LAYER met2 ;")
    lef.append("      RECT 0.600 0 16.600 %.3f ;" % met2_top)
    lef.append("      RECT 16.600 0 %.3f %.3f ;" % (TW, m2_vss))
    lef.append("      RECT 16.600 %.3f %.3f %.3f ;" % (q_hi, TW, met2_top))
    for g in range(STAGES):
        yx = g * PITCH + x_y
        lef.append("      RECT 0.090 %.3f 0.260 %.3f ;" % (yx - 0.085, yx + 0.085))
    lef.append("    LAYER met3 ;")
    lef.append("      RECT 0.600 0 %.3f %.3f ;" % (xsp - 0.20, H))
    lef.append("      RECT %.3f 0.750 %.3f %.3f ;" % (xsp - 0.20, xsp + 0.20, H))
    # channel met3 OBS stops 1.0um short of the corridor start (W): it used
    # to end exactly at W, touching the left edge of the VPWR/VGND power pins
    # and the corridor where pdngen builds the via towers, which blocked the
    # VPWR pin (PDN-0007) and prevented the repair from re-connecting the
    # cut VPWR strap (PSM-0069).
    lef.append("      RECT %.3f 0 %.3f %.3f ;" % (xsp + 0.20, W - 1.0, H))
    lef.append("    LAYER met4 ;")
    # met4 OBS: covers all internal met4 (channel spines, launch, A0/A1
    # hwires; the rightmost internal met4 ends at x=11.19, so the OBS edge
    # cannot be pulled left of W).  The VPWR strap at x=96.82 is cleared by
    # the macro placement (MACRO_X 83.30) + PDN_HORIZONTAL_HALO 0.3: the
    # OBS+halo+spacing edge lands at 94.88, 0.84um shy of the strap
    # obstruction (95.72).  VGND's strap (100.12) is far enough away and
    # survives.  Only the corridor x=W..TW stays open for the PDN straps.
    lef.append("      RECT 0 0 %.3f %.3f ;" % (W, H))
    lef.append("  END")
    lef.append("END %s" % name)
    lef.append("END LIBRARY")
    with open(os.path.join(out_dir, "arbchain.lef"), "w") as fh:
        fh.write("\n".join(lef) + "\n")

    # ---- black-box Verilog header (used by LibreLane synthesis) ----
    vh = []
    vh.append("`ifdef USE_POWER_PINS")
    vh.append("`celldefine")
    vh.append("module %s (" % name)
    vh.append("  output q,")
    vh.append("  input launch,")
    vh.append("  input arb_rst_n,")
    vh.append("  input [%d:0] ch," % (STAGES - 1))
    vh.append("  input VPWR,")
    vh.append("  input VGND")
    vh.append(");")
    vh.append("endmodule")
    vh.append("`endcelldefine")
    vh.append("`else")
    vh.append("module %s (" % name)
    vh.append("  output q,")
    vh.append("  input launch,")
    vh.append("  input arb_rst_n,")
    vh.append("  input [%d:0] ch" % (STAGES - 1))
    vh.append(");")
    vh.append("endmodule")
    vh.append("`endif")
    with open(os.path.join(out_dir, "arbchain.vh"), "w") as fh:
        fh.write("\n".join(vh) + "\n")

    # ---- gate-level netlist (internal cells) ----
    nl = []
    nl.append("// gate-level netlist of the arbchain macro (generated)")
    nl.append("module %s (" % name)
    nl.append("  output q,")
    nl.append("  input launch,")
    nl.append("  input arb_rst_n,")
    nl.append("  input [%d:0] ch," % (STAGES - 1))
    nl.append("  input VPWR,")
    nl.append("  input VGND")
    nl.append(");")
    nl.append("  wire [%d:0] top;" % STAGES)
    nl.append("  wire [%d:0] bot;" % STAGES)
    nl.append("  wire d, gate;")
    nl.append("  assign top[0] = launch;")
    nl.append("  assign bot[0] = launch;")

    def mux_inst(g, top_, inst, a, b, s, y):
        nl.append("  sky130_fd_sc_hd__mux2_1 %s (" % inst)
        nl.append("    .A0(%s), .A1(%s), .S(%s), .X(%s)," % (a, b, s, y))
        nl.append("    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)")
        nl.append("  );")

    for g in range(STAGES):
        if g == 0:
            a_t, b_t = "top[0]", "bot[0]"
            a_b, b_b = "bot[0]", "top[0]"
        else:
            a_t, b_t = "top[%d]" % g, "bot[%d]" % g
            a_b, b_b = "bot[%d]" % g, "top[%d]" % g
        mux_inst(g, True, "u_t%d" % g, a_t, b_t, "ch[%d]" % g, "top[%d]" % (g + 1))
        mux_inst(g, False, "u_b%d" % g, a_b, b_b, "ch[%d]" % g, "bot[%d]" % (g + 1))
    nl.append("  assign d = top[%d];" % STAGES)
    nl.append("  assign gate = bot[%d];" % STAGES)
    nl.append("  sky130_fd_sc_hd__dlrtp_1 u_latch (")
    nl.append("    .D(d), .GATE(gate), .RESET_B(arb_rst_n), .Q(q),")
    nl.append("    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)")
    nl.append("  );")
    nl.append("endmodule")
    with open(os.path.join(out_dir, "arbchain.nl.v"), "w") as fh:
        fh.write("\n".join(nl) + "\n")

    # ---- behavioural model (RTL simulation only) ----
    bv = []
    bv.append("`timescale 1ns/1ps")
    bv.append("// behavioural model of the arbchain macro (RTL simulation only)")
    bv.append("module %s (" % name)
    bv.append("  q, launch, arb_rst_n, ch")
    bv.append(");")
    bv.append("  output q;")
    bv.append("  input launch;")
    bv.append("  input arb_rst_n;")
    bv.append("  input [%d:0] ch;" % (STAGES - 1))
    bv.append("")
    bv.append("  wire top_out, bot_out;")
    bv.append("")
    bv.append("  arbiter_chain #(.STAGES(%d), .IDX(0)) u_chain (" % STAGES)
    bv.append("    .launch(launch), .ch(ch), .top_out(top_out), .bot_out(bot_out)")
    bv.append("  );")
    bv.append("")
    bv.append("  arbiter_cell u_arbiter (")
    bv.append("    .top_in(top_out), .bot_in(bot_out), .arb_rst_n(arb_rst_n), .q(q)")
    bv.append("  );")
    bv.append("endmodule")
    with open(os.path.join(out_dir, "arbchain.v"), "w") as fh:
        fh.write("\n".join(bv) + "\n")

    print("wrote arbchain.lef / .vh / .nl.v / .v")


if __name__ == "__main__":
    main()
