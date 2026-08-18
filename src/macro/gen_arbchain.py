#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# gen_arbchain.py (Rewritten & Fixed)
#
# Generates the "arbchain" symmetric hard macro for the
# arbiter PUF switch chain.
#
# FIXES APPLIED:
# 1. Separated `q` and `arb_rst_n` onto different met3 tracks to prevent shorting.
# 2. Fixed met4 OBS to leave an access window for the `launch` pin.
# 3. Unified Verilog views (.vh, .nl.v, .v) to all support `USE_POWER_PINS`.
# 4. Dynamically passed pin coordinates from layout to LEF generation to prevent drift.
# 5. Removed the redundant and conflicting PR boundary hack at the end of the script.
# ============================================================

import argparse
import os
import re
import sys
import json
import urllib.request
import klayout.db as pya

# pinned cell sources (google/skywater-pdk-libs-sky130_fd_sc_hd)
CELL_FILES = {
    "sky130_fd_sc_hd__mux2_1.gds": "cells/mux2/sky130_fd_sc_hd__mux2_1.gds",
    "sky130_fd_sc_hd__mux2_1.lef": "cells/mux2/sky130_fd_sc_hd__mux2_1.lef",
    "sky130_fd_sc_hd__dlrtp_1.gds": "cells/dlrtp/sky130_fd_sc_hd__dlrtp_1.gds",
    "sky130_fd_sc_hd__dlrtp_1.lef": "cells/dlrtp/sky130_fd_sc_hd__dlrtp_1.lef",
}
CELL_BASE = ("https://raw.githubusercontent.com/google/"
             "skywater-pdk-libs-sky130_fd_sc_hd/main/")

def ensure_cells(gds_dir, lef_dir):
    """Return (gds_dir, lef_dir) that actually contain the cells."""
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
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
STAGES = 24
MUX_W = 4.14          
MUX_H = 2.72          
LATCH_W = 5.98        
LATCH_H = 2.72
PITCH = 3.40          
GAP = 1.5             
CH = 2 * GAP          
W = 2 * (GAP + MUX_W) 
XC = W / 2            
YOFF = 0.24           
H = (STAGES + 1) * PITCH + 2 * YOFF  

MUX_LEF = "sky130_fd_sc_hd__mux2_1"
LATCH_LEF = "sky130_fd_sc_hd__dlrtp_1"

LAY_LI1  = (67, 20)
LAY_MET1 = (68, 20)
LAY_MET2 = (69, 20)
LAY_MET3 = (70, 20)
LAY_MET4 = (71, 20)
LAY_VIA  = (67, 44)   
LAY_VIA2 = (68, 44)   
LAY_VIA3 = (69, 44)   
LAY_VIA4 = (70, 44)   
LAY_PR   = (236, 0)   

EV = {"a0": 0.8, "a1t": 0.40, "a1b": 0.74, "x": 1.26, "ch": 1.06}
OD = {"a0": 0.8, "a1t": 0.40, "a1b": 0.74, "x": 1.26, "ch": 1.06}

STRAPS = {
    "VSS_L": 4.70, "VDD_L": 5.10,
    "VDD_R": 6.48, "VSS_R": 6.88,
}
PAIR_A = (5.34, 5.94)
PAIR_B = (4.94, 6.34)

MACRO_X = 83.30                          
MACRO_Y = 7.20                           
CORR_W = 6.00                            
TW = W + CORR_W                          

VP_RAIL = (H - 0.70, H)                  
VP_RAIL_X = 14.95                        
VG_RAIL = (H - 0.68, H - 0.01)           
VG_RAIL_X0 = STRAPS["VSS_R"] - 0.09      

ACCESS_MAX = 1.34
VIA = 0.170           
M2W = 0.170           

def pt(x, y):
    return (round(x * 1000), round(y * 1000))

class Cell:
    def __init__(self, name, gds_path, lef_path):
        self.name = name
        self.gds_path = gds_path
        self.lef_path = lef_path
        self.pins = {}       
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
                if m: cur = None
                m = re.search(r"PIN\s+(\S+)", line)
                if m:
                    cur = m.group(1)
                    self.pins.setdefault(cur, [])
                m = re.search(r"LAYER\s+(\S+)\s*;", line)
                if m and cur: self._layer = m.group(1)
                m = re.match(r"\s*SIZE\s+([\d.\-]+)\s+BY\s+([\d.\-]+)\s*;", line)
                if m: self.size = (float(m.group(1)), float(m.group(2)))
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
        metals = {
            "li1":  self._region(67, 20), "met1": self._region(68, 20),
            "met2": self._region(69, 20), "met3": self._region(70, 20),
        }
        cuts = {
            "via":  self._region(67, 44), "via2": self._region(68, 44), "via3": self._region(69, 44)
        }
        polys = {}
        uf = _UF()
        nid = 0
        for name, reg in metals.items():
            polys[name] = []
            for po in reg.each():
                polys[name].append((nid, po))
                uf.nodes.append(nid)
                nid += 1
        for (cn, la, lb) in [("via", "li1", "met1"), ("via2", "met1", "met2"), ("via3", "met2", "met3")]:
            for cp in cuts[cn].each():
                ids = []
                creg = pya.Region(cp)
                for (i, p) in polys[la]:
                    if not (pya.Region(p) & creg).is_empty(): ids.append(i)
                for (i, p) in polys[lb]:
                    if not (pya.Region(p) & creg).is_empty(): ids.append(i)
                if ids:
                    for i in ids[1:]: uf.union(ids[0], i)
        self.pin_metal = {}
        for pin in self.pins:
            comps = set()
            for (layer, r) in self.pins[pin]:
                if layer != "li1": continue
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
                    if uf.find(i) in comps: reg.insert(po)
            reg.merge()
            self.pin_metal[pin] = reg

    def other_pin_metal(self, pin):
        reg = pya.Region()
        for p, r in self.pin_metal.items():
            if p != pin: reg += r
        return reg.merged()

    def bbox_um(self):
        b = self.cell.bbox()
        return (b.left * self.dbu, b.bottom * self.dbu, b.right * self.dbu, b.top * self.dbu)

class Draw:
    def __init__(self, ly, top):
        self.ly = ly
        self.top = top
        self.layers = {}
        self.shapes = []   

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

MET4_YOFF, MET4_YPITCH = 0.46, 0.92
MET3_XOFF, MET3_XPITCH = 0.34, 0.68

def snap_met3_y(y_local):
    g = MACRO_Y + y_local
    return MET3_XOFF + MET3_XPITCH * round((g - MET3_XOFF) / MET3_XPITCH) - MACRO_Y

def snap_met4_x(x_local):
    g = MACRO_X + x_local
    return MET4_YOFF + MET4_YPITCH * round((g - MET4_YOFF) / MET4_YPITCH) - MACRO_X

def top_trans(g):
    y = g * PITCH + YOFF
    return pya.Trans(0, False, 0, round(y * 1000))

def bot_trans(g):
    y = g * PITCH + YOFF
    return pya.Trans(0, False, round(W * 1000), round(y * 1000)) * pya.Trans.M90

def latch_trans(y):
    x0 = (W - LATCH_W) / 2
    return pya.Trans(0, False, round(x0 * 1000), round(y * 1000))

def pin_rects_um(cell, trans, pin):
    out = []
    dbu = cell.dbu
    for _, r in cell.pins.get(pin, []):
        b = pya.Box(round(r[0] / dbu), round(r[1] / dbu), round(r[2] / dbu), round(r[3] / dbu))
        b = b.transformed(trans)
        out.append((b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu))
    return out

def pin_rects_um_layer(cell, trans, pin):
    out = []
    dbu = cell.dbu
    for layer, r in cell.pins.get(pin, []):
        b = pya.Box(round(r[0] / dbu), round(r[1] / dbu), round(r[2] / dbu), round(r[3] / dbu))
        b = b.transformed(trans)
        out.append((layer, (b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu)))
    return out

def safe_access(cell, trans, pin, y_track):
    body = pya.Box(0, 0, int(cell.size[0] / cell.dbu), int(cell.size[1] / cell.dbu))
    tb = body.transformed(trans)
    cell_bottom = tb.bottom * cell.dbu
    acc_max = cell_bottom + ACCESS_MAX
    rects = pin_rects_um(cell, trans, pin)
    rects = [r for r in rects if r[2] - r[0] >= VIA - 0.001]
    for r in rects:
        y_lo = r[1] + VIA / 2 + 0.02
        y_hi = min(r[3] - VIA / 2 - 0.02, acc_max)
        if y_lo <= y_track <= y_hi:
            x = (r[0] + r[2]) / 2
            x = max(r[0] + VIA / 2, min(r[2] - VIA / 2, x))
            return (x, y_track)
    for r in rects:
        y_lo = r[1] - VIA / 2 + 0.03
        y_hi = min(r[3], acc_max - VIA / 2 - 0.01)
        if y_hi < y_lo: continue
        y = max(y_lo, min(y_track, y_hi))
        if not (y + VIA / 2 >= r[1] - 0.005 and y - VIA / 2 <= r[3] + 0.005): continue
        x = (r[0] + r[2]) / 2
        x = max(r[0] + VIA / 2, min(r[2] - VIA / 2, x))
        return (x, y)
    return None

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

    mux = Cell(MUX_LEF, os.path.join(gds_dir, "sky130_fd_sc_hd__mux2_1.gds"), os.path.join(lef_dir, "sky130_fd_sc_hd__mux2_1.lef"))
    latch = Cell(LATCH_LEF, os.path.join(gds_dir, "sky130_fd_sc_hd__dlrtp_1.gds"), os.path.join(lef_dir, "sky130_fd_sc_hd__dlrtp_1.lef"))

    ly = pya.Layout()
    ly.dbu = 0.001
    macro = ly.create_cell("arbchain")
    d = Draw(ly, macro)
    ly.read(mux.gds_path)
    ly.read(latch.gds_path)
    mux_ref = ly.cell(mux.name)
    latch_ref = ly.cell(latch.name)

    for g in range(STAGES):
        macro.insert(pya.CellInstArray(mux_ref, top_trans(g)))
        macro.insert(pya.CellInstArray(mux_ref, bot_trans(g)))
    
    ly_r = STAGES * PITCH + YOFF
    macro.insert(pya.CellInstArray(latch_ref, latch_trans(ly_r)))

    def viat(x, y): d.box(LAY_VIA, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)
    def via2(x, y): d.box(LAY_VIA2, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)
    def via3(x, y): d.box(LAY_VIA3, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)
    def via4(x, y): d.box(LAY_VIA4, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)
    def pad(layer, x, y): d.box(layer, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)

    def tap_m3(cell, trans, pin, y_track):
        pt = safe_access(cell, trans, pin, y_track)
        if pt is None: return None
        x, y = pt
        viat(x, y); pad(LAY_MET1, x, y); via2(x, y); pad(LAY_MET2, x, y); via3(x, y); pad(LAY_MET3, x, y)
        return (x, y)

    def tap_m4(cell, trans, pin, y_track):
        pt = safe_access(cell, trans, pin, y_track)
        if pt is None: return None
        x, y = pt
        viat(x, y); pad(LAY_MET1, x, y); via2(x, y); pad(LAY_MET2, x, y); via3(x, y); pad(LAY_MET3, x, y); via4(x, y); pad(LAY_MET4, x, y)
        return (x, y)

    def tap_m3_pin(cell, trans, pin, y_track, to_y=None):
        pt = safe_access(cell, trans, pin, y_track)
        if pt is None: return None
        x, y = pt
        ys = snap_met3_y(y) if to_y is None else to_y
        viat(x, y); pad(LAY_MET1, x, y); via2(x, y); pad(LAY_MET2, x, y)
        if abs(ys - y) > 0.0005:
            y0, y1 = (ys, y) if ys < y else (y, ys)
            d.v(LAY_MET2, x, y0, y1)
        via3(x, ys); pad(LAY_MET3, x, ys)
        return (x, ys)

    def spine(layer, x, y0, y1):
        if y1 < y0: y0, y1 = y1, y0
        d.v(layer, x, y0, y1)

    def hwire(layer, y, x0, x1):
        if x1 < x0: x0, x1 = x1, x0
        d.h(layer, y, x0, x1)

    tc0 = row_tracks(0)
    yc0 = YOFF + tc0["ch"]
    s1 = tap_m3(mux, top_trans(0), "S", yc0)
    s2 = tap_m3(mux, bot_trans(0), "S", yc0)
    if s1 and s2: hwire(LAY_MET3, yc0, 0.0, s2[0])

    for g in range(1, STAGES):
        y_prev = (g - 1) * PITCH + YOFF
        y_cur = g * PITCH + YOFF
        tp = row_tracks(g - 1)
        tc = row_tracks(g)
        X_T, X_B = PAIR_A if g % 2 == 0 else PAIR_B

        src = tap_m4(mux, top_trans(g - 1), "X", y_prev + tp["x"])
        a0 = tap_m4(mux, top_trans(g), "A0", y_cur + tc["a0"])
        a1 = tap_m3(mux, bot_trans(g), "A1", y_cur + tc["a1b"])
        if src and a0 and a1:
            sxs, sysy = src; a0x, a0y = a0; a1x, a1y = a1
            hwire(LAY_MET4, sysy, sxs, X_T); spine(LAY_MET4, X_T, sysy, a0y); spine(LAY_MET4, X_T, sysy, a1y)
            hwire(LAY_MET4, a0y, a0x, X_T); hwire(LAY_MET3, a1y, X_T, a1x); via4(X_T, a1y)

        src = tap_m4(mux, bot_trans(g - 1), "X", y_prev + tp["x"])
        a1 = tap_m3(mux, top_trans(g), "A1", y_cur + tc["a1t"])
        a0 = tap_m4(mux, bot_trans(g), "A0", y_cur + tc["a0"])
        if src and a1 and a0:
            sxs, sysy = src; a1x, a1y = a1; a0x, a0y = a0
            hwire(LAY_MET4, sysy, X_B, sxs); spine(LAY_MET4, X_B, sysy, a1y); spine(LAY_MET4, X_B, sysy, a0y)
            hwire(LAY_MET3, a1y, a1x, X_B); via4(X_B, a1y); hwire(LAY_MET4, a0y, X_B, a0x)

        yc = y_cur + tc["ch"]
        s1 = tap_m3(mux, top_trans(g), "S", yc)
        s2 = tap_m3(mux, bot_trans(g), "S", yc)
        if s1 and s2: hwire(LAY_MET3, yc, 0.0, s2[0])

    tc0 = row_tracks(0)
    y0 = YOFF
    xc = snap_met4_x(XC)
    la0 = tap_m4(mux, top_trans(0), "A0", y0 + tc0["a0"])
    lb0 = tap_m4(mux, bot_trans(0), "A0", y0 + tc0["a0"])
    la1 = tap_m3(mux, top_trans(0), "A1", y0 + tc0["a1t"])
    lb1 = tap_m3(mux, bot_trans(0), "A1", y0 + tc0["a1b"])
    ys = []
    if la0 and lb0:
        hwire(LAY_MET4, la0[1], la0[0], xc); hwire(LAY_MET4, lb0[1], xc, lb0[0]); ys.append(la0[1])
    if la1 and lb1:
        hwire(LAY_MET3, la1[1], la1[0], xc); via4(xc, la1[1]); hwire(LAY_MET3, lb1[1], xc, lb1[0]); via4(xc, lb1[1]); ys.extend([la1[1], lb1[1]])
    if ys:
        spine(LAY_MET4, xc, 0.15, max(ys))
        d.box(LAY_MET4, xc - 0.17 / 2, 0, xc + 0.17 / 2, 0.70)

    ylat = ly_r
    tp = row_tracks(STAGES - 1)
    X_T, X_B = PAIR_A
    src = tap_m4(mux, top_trans(STAGES - 1), "X", ylat - PITCH + tp["x"])
    dpt = tap_m3(latch, latch_trans(ylat), "D", ylat + 1.2)
    if src and dpt:
        sxs, sysy = src; dx, dy = dpt
        hwire(LAY_MET4, sysy, sxs, X_T); spine(LAY_MET4, X_T, sysy, dy); hwire(LAY_MET3, dy, dx, X_T); via4(X_T, dy)

    src = tap_m4(mux, bot_trans(STAGES - 1), "X", ylat - PITCH + tp["x"])
    gpt = tap_m3(latch, latch_trans(ylat), "GATE", ylat + 1.0)
    if src and gpt:
        sxs, sysy = src; gx, gy = gpt
        hwire(LAY_MET4, sysy, X_B, sxs); spine(LAY_MET4, X_B, sysy, gy); hwire(LAY_MET3, gy, gx, X_B); via4(X_B, gy)

        # [FIX 1] 强制分离 q 和 arb_rst_n 的 met3 track，防止短路
    # 计算最接近 latch 中部的 met3 track 索引，并强制分配相邻的两个 track
    y_mid = ylat + 0.50
    g_mid = MACRO_Y + y_mid
    idx_mid = round((g_mid - MET3_XOFF) / MET3_XPITCH)
    
    idx_q = idx_mid
    idx_rst = idx_mid + 1  # 强制使用上一根 track，保证物理间距为 0.68um (一个完整 pitch)
    
    # 通过索引反推精确的 Y 坐标
    q_track = MET3_XOFF + MET3_XPITCH * idx_q - MACRO_Y
    rst_track = MET3_XOFF + MET3_XPITCH * idx_rst - MACRO_Y
    
    # 断言检查，确保两者不在同一条 track 上 (间距 >= 0.67um)
    assert abs(q_track - rst_track) >= 0.67, \
        f"CRITICAL: q and arb_rst_n tracks too close or identical! q={q_track}, rst={rst_track}"

    # 将 pin 连接到各自的独立 track 上
    qpt = tap_m3_pin(latch, latch_trans(ylat), "Q", q_track, to_y=q_track)
    if qpt: hwire(LAY_MET3, qpt[1], qpt[0], TW)

    rpt = tap_m3_pin(latch, latch_trans(ylat), "RESET_B", rst_track, to_y=rst_track)
    if rpt: hwire(LAY_MET3, rpt[1], 0, rpt[0])
    # --- power ---
    for name, x in STRAPS.items():
        d.v(LAY_MET1, x, 0, H)

    def rail_bands(cell, tr, pin):
        out = set()
        for (layer, r) in pin_rects_um_layer(cell, tr, pin):
            if layer == "met1" and (r[2] - r[0]) >= MUX_W - 0.01:
                out.add((round(r[1], 3), round(r[3], 3)))
        return out

    for g in range(STAGES):
        y = g * PITCH + YOFF
        t = top_trans(g)
        b = bot_trans(g)
        bands = {}  
        for tr in (t, b):
            for net, pin in (("VDD", "VPWR"), ("VSS", "VGND")):
                bands.setdefault(net, set()).update(rail_bands(mux, tr, pin))
        for net, ys in bands.items():
            for (y0, y1) in ys:
                ym = (y0 + y1) / 2
                if ym <= y + MUX_H + 0.01:  
                    d.h(LAY_MET2, ym, 0, TW)
        for (tr, sx) in ((t, STRAPS["VDD_L"]), (t, STRAPS["VSS_L"]), (b, STRAPS["VDD_R"]), (b, STRAPS["VSS_R"])):
            net = "VDD" if sx in (STRAPS["VDD_L"], STRAPS["VDD_R"]) else "VSS"
            pin = "VPWR" if net == "VDD" else "VGND"
            for (y0, y1) in rail_bands(mux, tr, pin):
                via2(sx, (y0 + y1) / 2)

    ylat = STAGES * PITCH + YOFF
    for (pin, net) in (("VPWR", "VDD"), ("VGND", "VSS")):
        s1 = STRAPS["VDD_L"] if net == "VDD" else STRAPS["VSS_L"]
        for (y0, y1) in rail_bands(latch, latch_trans(ylat), pin):
            ym = (y0 + y1) / 2
            d.h(LAY_MET2, ym, s1, TW)
            via2(s1, ym)

    d.box(LAY_MET2, 0, VP_RAIL[0], VP_RAIL_X, VP_RAIL[1])
    d.box(LAY_MET1, VG_RAIL_X0, VG_RAIL[0], TW, VG_RAIL[1])
    for sx in (STRAPS["VDD_L"], STRAPS["VDD_R"]):
        if sx < VP_RAIL_X:
            via2(sx, (VP_RAIL[0] + VP_RAIL[1]) / 2)

    d.box(LAY_PR, 0, 0, TW, H)

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    gds = os.path.join(out_dir, "arbchain.gds")
    ly.write(gds)
    print("wrote", gds)

    with open(os.path.join(out_dir, "arbchain_routing.json"), "w") as fh:
        json.dump([{"layer": list(layer), "box": [round(v, 3) for v in box]} for layer, box in d.shapes], fh)

    # [FIX 4] 动态传递 Pin 坐标给 LEF 生成，防止漂移
    pin_coords = {
        "q_y": q_track,
        "rst_y": rst_track,
        "launch_x": xc,
        "launch_y": 0.70
    }
    emit_artifacts(out_dir, pin_coords)

def emit_artifacts(out_dir, pin_coords):
    name = "arbchain"
    lat = STAGES * PITCH + YOFF

    def ch_y(g):
        return g * PITCH + YOFF + EV["ch"]

    def pin_rect(layer, x1, y1, x2, y2):
        return (layer, (x1, y1, x2, y2))

    lef_pins = []
    for g in range(STAGES):
        lef_pins.append(("ch[%d]" % g, "INPUT", "SIGNAL", [pin_rect("met3", 0.0, ch_y(g) - 0.15, 0.30, ch_y(g) + 0.15)]))
    
    xsp = pin_coords["launch_x"]
    lef_pins.append(("launch", "INPUT", "SIGNAL", [pin_rect("met4", xsp - 0.15, 0.0, xsp + 0.15, 0.70)]))
    
    # 使用动态传入的坐标
    lef_pins.append(("arb_rst_n", "INPUT", "SIGNAL", [pin_rect("met3", 0.0, pin_coords["rst_y"] - 0.15, 0.30, pin_coords["rst_y"] + 0.15)]))
    lef_pins.append(("q", "OUTPUT", "SIGNAL", [pin_rect("met3", TW - 0.68, pin_coords["q_y"] - 0.15, TW, pin_coords["q_y"] + 0.15)]))
    
    lef_pins.append(("VPWR", "INOUT", "POWER", [pin_rect("met2", W, VP_RAIL[0], TW, VP_RAIL[1])]))
    lef_pins.append(("VGND", "INOUT", "GROUND", [pin_rect("met1", W, VG_RAIL[0], TW, VG_RAIL[1])]))

    lef = ["# LEF abstract of the arbchain macro (generated)", "VERSION 5.8 ;", "BUSBITCHARS \"[]\" ;", "DIVIDERCHAR \"/\" ;",
           "MACRO %s" % name, "  CLASS BLOCK ;", "  ORIGIN 0 0 ;", "  SIZE %.3f BY %.3f ;" % (TW, H), "  SYMMETRY X Y ;"]
    
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

    qy = pin_coords["q_y"]
    x_y = EV["x"] + YOFF  
    met1_top = VG_RAIL[0]   
    met2_top = VP_RAIL[0]   
    q_x = TW - 0.90        
    q_hi = lat + 2.00      
    m1_vss = lat + 0.24    
    m2_vss = lat + 0.085   

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
    lef.append("      RECT %.3f 0 %.3f %.3f ;" % (xsp + 0.20, W - 1.0, H))
    
    # [FIX 2] 修复 met4 OBS，为 launch pin 留出 Access Window
    lef.append("    LAYER met4 ;")
    lef.append("      RECT 0 0 %.3f %.3f ;" % (xsp - 0.25, H))                 # 左侧 Block
    lef.append("      RECT %.3f 0.75 %.3f %.3f ;" % (xsp - 0.25, xsp + 0.25, H)) # 上方 Block
    lef.append("      RECT %.3f 0 %.3f %.3f ;" % (xsp + 0.25, W, H))             # 右侧 Block
    
    lef.append("  END")
    lef.append("END %s" % name)
    lef.append("END LIBRARY")
    with open(os.path.join(out_dir, "arbchain.lef"), "w") as fh:
        fh.write("\n".join(lef) + "\n")

    vh = []
    vh.append("`ifdef USE_POWER_PINS")
    vh.append("`celldefine")
    vh.append("module %s (" % name)
    vh.append("  output q, input launch, input arb_rst_n, input [%d:0] ch," % (STAGES - 1))
    vh.append("  input VPWR, input VGND")
    vh.append(");")
    vh.append("endmodule")
    vh.append("`endcelldefine")
    vh.append("`else")
    vh.append("module %s (" % name)
    vh.append("  output q, input launch, input arb_rst_n, input [%d:0] ch" % (STAGES - 1))
    vh.append(");")
    vh.append("endmodule")
    vh.append("`endif")
    with open(os.path.join(out_dir, "arbchain.vh"), "w") as fh:
        fh.write("\n".join(vh) + "\n")

    # [FIX 3] 统一网表视图，支持 USE_POWER_PINS
    nl = []
    nl.append("// gate-level netlist of the arbchain macro (generated)")
    nl.append("`ifdef USE_POWER_PINS")
    nl.append("`celldefine")
    nl.append("module %s (" % name)
    nl.append("  output q, input launch, input arb_rst_n, input [%d:0] ch," % (STAGES - 1))
    nl.append("  input VPWR, input VGND")
    nl.append(");")
    nl.append("`else")
    nl.append("module %s (" % name)
    nl.append("  output q, input launch, input arb_rst_n, input [%d:0] ch" % (STAGES - 1))
    nl.append(");")
    nl.append("`endif")
    
    nl.append("  wire [%d:0] top;" % STAGES)
    nl.append("  wire [%d:0] bot;" % STAGES)
    nl.append("  wire d, gate;")
    nl.append("  assign top[0] = launch;")
    nl.append("  assign bot[0] = launch;")
    
    def mux_inst(g, top_, inst, a, b, s, y):
        nl.append("  sky130_fd_sc_hd__mux2_1 %s (" % inst)
        nl.append("    .A0(%s), .A1(%s), .S(%s), .X(%s)" % (a, b, s, y))
        nl.append("`ifdef USE_POWER_PINS")
        nl.append("    , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)")
        nl.append("`endif")
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
    nl.append("    .D(d), .GATE(gate), .RESET_B(arb_rst_n), .Q(q)")
    nl.append("`ifdef USE_POWER_PINS")
    nl.append("    , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)")
    nl.append("`endif")
    nl.append("  );")
    nl.append("endmodule")
    nl.append("`endcelldefine")
    with open(os.path.join(out_dir, "arbchain.nl.v"), "w") as fh:
        fh.write("\n".join(nl) + "\n")

    bv = []
    bv.append("`timescale 1ns/1ps")
    bv.append("// behavioural model of the arbchain macro (RTL simulation only)")
    bv.append("`ifdef USE_POWER_PINS")
    bv.append("module %s (q, launch, arb_rst_n, ch, VPWR, VGND);" % name)
    bv.append("`else")
    bv.append("module %s (q, launch, arb_rst_n, ch);" % name)
    bv.append("`endif")
    bv.append("  output q; input launch; input arb_rst_n; input [%d:0] ch;" % (STAGES - 1))
    bv.append("  wire top_out, bot_out;")
    bv.append("  arbiter_chain #(.STAGES(%d), .IDX(0)) u_chain (.launch(launch), .ch(ch), .top_out(top_out), .bot_out(bot_out));" % STAGES)
    bv.append("  arbiter_cell u_arbiter (.top_in(top_out), .bot_in(bot_out), .arb_rst_n(arb_rst_n), .q(q));")
    bv.append("endmodule")
    with open(os.path.join(out_dir, "arbchain.v"), "w") as fh:
        fh.write("\n".join(bv) + "\n")

    print("wrote arbchain.lef / .vh / .nl.v / .v")

if __name__ == "__main__":
    main()