#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# check_chain_delay.py
#
# Pure-GDS theoretical-delay checker for the two racing mux chains
# of the arbiter hard macro.
#
# The macro contains two mux chains (left "top" race and right "bot"
# race).  For the race to be trustworthy, the two chains must be
# physically symmetric: the same metal routing length per stage, the
# same vias and the same pin pads on both sides.  Any asymmetry gives
# one side a systematic fixed advantage; the race then no longer
# measures the same thing twice.  This tool measures the GDS *as
# drawn* and reports whether the two chains are theoretically
# delay-equal within --tol.
#
# IMPORTANT: the script reads ONLY the GDS plus the sky130 cell LEF/GDS
# files (standard-cell library data used to place pin coordinates).  It
# does NOT read or import the macro generator script (gen_arbchain*.py)
# and it does not depend on any generator-internal layout parameter.
#
# Method:
#   1. Read the GDS; take the top cell; collect the drawn metal shapes
#      (met1-4 + the via cut layers) and the mux/latch cell instances.
#   2. Build the conductive graph: same-layer shapes merge; via cut
#      boxes bridge the two adjacent metal layers (MCON: li1-met1,
#      via1: met1-met2, via2: met2-met3, via3: met3-met4).
#   3. Recover the netlist purely from geometry:
#      - rows: mux instances clustered by centre y -> stage count
#      - columns: two per row, by centre x
#      - pin location per instance: largest li1 polygon inside the LEF
#        pin rect, transformed into macro coords
#      - the intended arbiter nets:
#          ch[g]   = S pin of left+right mux of row g
#          top[g]  = X(left g-1) + A0(left g) + A1(right g)
#          bot[g]  = X(right g-1) + A1(left g) + A0(right g)
#          launch  = A0 + A1 of both columns, row 0
#          top[N+1]= X(left N-1) + latch D
#          bot[N+1]= X(right N-1) + latch GATE
#   4. Net integrity: every member of a net must be in exactly one
#      conductive component; no net may touch VDD/VSS.
#   5. Delay index per net (Elmore-style RC wire model):
#        L(layer) = area / WIRE_W[layer]              (um)
#        R = sum(rho_sheet[l] * L / w) + sum(vias)*rho_via
#        C = c_um * sum(L) + n_pins * c_pin
#        tau = 0.5 * R * C
#   6. Compare the two chains *as built*:
#         top_chain = tau(launch) + sum tau(top[g]) + tau(top[N+1])
#         bot_chain = tau(launch) + sum tau(bot[g]) + tau(bot[N+1])
#      Pass only if every pair is within --tol % and nets are intact.
#
# Usage:
#   python check_chain_delay.py [arbchain.gds] \
#       --cell-gds-dir DIR --cell-lef-dir DIR [--tol 1.0] \
#       [--rho-sheet "met2:0.024,met3:0.024,met4:0.53"] \
#       [--rho-via 1.0] [--c-um 0.00012] [--c-pin 0.05]
# ============================================================

import argparse
import os
import re
import sys

import klayout.db as pya

# ------------------------------------------------------------------
# sky130 semantic layers
# ------------------------------------------------------------------
LI1 = (67, 20)
MET1 = (68, 20)
MET2 = (69, 20)
MET3 = (70, 20)
MET4 = (71, 20)
MCON = (67, 44)
VIA1L = (68, 44)
VIA2L = (69, 44)
VIA3L = (70, 44)

METALS = [MET1, MET2, MET3, MET4]

# nominal wire width per metal layer (um); used to turn area into length
WIRE_W = {MET1: 0.15, MET2: 0.17, MET3: 0.30, MET4: 0.30}

# sheet resistance (ohm / square) per layer, sky130-ish defaults
RHO_SHEET = {MET1: 0.024, MET2: 0.024, MET3: 0.024, MET4: 0.53}
RHO_VIA = 1.0          # ohms per via stack
C_UM = 0.12e-3         # fF per um of wire
C_PIN = 0.05           # fF per external pin

VIA_PAIRS = {MCON: (LI1, MET1), VIA1L: (MET1, MET2),
             VIA2L: (MET2, MET3), VIA3L: (MET3, MET4)}
VIA_R = {MCON: 0.4, VIA1L: 2.0, VIA2L: 2.0, VIA3L: 2.0}


def overlap1(a1, a2, b1, b2):
    return max(a1, b1) < min(a2, b2)


def hit(b1, b2):
    return (overlap1(b1[0], b1[2], b2[0], b2[2]) and
            overlap1(b1[1], b1[3], b2[1], b2[3]))


def read_lef_pins(lef_path):
    """{pin: [ (layer, (x1,y1,x2,y2)), ... ]} from a sky130 cell LEF."""
    pins = {}
    cur = None
    for line in open(lef_path):
        m = re.match(r"\s*PIN\s+(\S+)", line)
        if m:
            cur = m.group(1)
            pins.setdefault(cur, [])
            continue
        la = re.findall(r"LAYER\s+(\S+)\s*;", line)
        rb = re.match(r"\s*RECT\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*;", line)
        if la:
            curlayer = la[0]
            continue
        if rb and cur is not None:
            pins[cur].append((curlayer, tuple(float(rb.group(i)) for i in range(1, 5))))
        if line.startswith("END"):
            cur = None
    return pins


def boxes_for_layer(cell, ly, dbu, sem):
    """un-merged (x0,y0,x1,y1) boxes of one semantic layer of a cell,
    in um (lattice * dbu)."""
    boxes = []
    it = cell.begin_shapes_rec(ly.layer(*sem))
    while not it.at_end():
        b = it.shape().bbox()
        boxes.append((b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu))
        it.next()
    return boxes


class CellGeom:
    """sky130 cell + LEF pin placement (standalone, no generator)."""

    def __init__(self, name, gds_path, lef_path):
        self.name = name
        self.lef_pins = read_lef_pins(lef_path)
        self.ly = pya.Layout()
        self.ly.read(gds_path)
        self.cell = self.ly.cell(name)
        if self.cell is None:
            sys.exit(f"cell {name} not found in {gds_path}")
        self.dbu = self.ly.dbu
        self._li1c = {}

    def li1_region(self, trans):
        k = trans.to_s()
        if k not in self._li1c:
            r = pya.Region()
            it = self.cell.begin_shapes_rec(self.ly.layer(*LI1))
            while not it.at_end():
                r.insert(it.shape().bbox().transformed(trans))
                it.next()
            self._li1c[k] = r.merged()
        return self._li1c[k]

    def pin_rects(self, pin, trans):
        out = []
        for (layer, r) in self.lef_pins.get(pin, []):
            if layer != "li1":
                continue
            b = pya.Box(int(r[0] / self.dbu), int(r[1] / self.dbu),
                        int(r[2] / self.dbu), int(r[3] / self.dbu)).transformed(trans)
            out.append((b.left * self.dbu, b.bottom * self.dbu,
                        b.right * self.dbu, b.top * self.dbu))
        return out

    def pin_center(self, pin, trans):
        best = None
        best_a = 0.0
        li = self.li1_region(trans)
        for (x0, y0, x1, y1) in self.pin_rects(pin, trans):
            rb = pya.Box(int(x0 / self.dbu), int(y0 / self.dbu),
                         int(x1 / self.dbu), int(y1 / self.dbu))
            inter = (pya.Region(rb) & li).merged()
            for po in inter.each():
                a = po.area()
                if a > best_a:
                    best_a = a
                    best = po.bbox()
        if best is None:
            return None
        return (best.center().x * self.dbu, best.center().y * self.dbu)


class ConGraph:
    """Union-find over drawn boxes (one node per box)."""

    def __init__(self):
        self.p = []
        self.lay = []
        self.box = []

    def add(self, layer, bx):
        nid = len(self.p)
        self.p.append(nid)
        self.lay.append(layer)
        self.box.append(bx)
        return nid

    def area(self, nid):
        bx = self.box[nid]
        return (bx[2] - bx[0]) * (bx[3] - bx[1])

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def build_graph(top, ly, dbu):
    g = ConGraph()
    metal_nodes = {m: [] for m in METALS}
    for sem in METALS:
        for bx in boxes_for_layer(top, ly, dbu, sem):
            metal_nodes[sem].append(g.add(sem, bx))
    # same-layer overlap = same conductor
    for sem in METALS:
        ns = metal_nodes[sem]
        for i in range(len(ns)):
            for j in range(i + 1, len(ns)):
                if hit(g.box[ns[i]], g.box[ns[j]]):
                    g.union(ns[i], ns[j])
    # via cuts bridge adjacent layers
    for cut, (la, lb) in VIA_PAIRS.items():
        cut_nodes = [g.add(("CUT", cut), bx)
                     for bx in boxes_for_layer(top, ly, dbu, cut)]
        for cid in cut_nodes:
            for sem in (la, lb):
                if sem in METALS:
                    for m in metal_nodes[sem]:
                        if hit(g.box[cid], g.box[m]):
                            g.union(cid, m)
    return g


class ArbChecker:
    def __init__(self, gds_path, cell_dir, lef_dir,
                 rho_sheet=None, rho_via=None, c_um=None, c_pin=None):
        self.gds_path = gds_path
        self.cell_dir = cell_dir or os.path.dirname(gds_path)
        self.lef_dir = lef_dir or self.cell_dir
        self.RHO = dict(rho_sheet if rho_sheet is not None else RHO_SHEET)
        self.RVIA = rho_via if rho_via is not None else RHO_VIA
        self.CUM = c_um if c_um is not None else C_UM
        self.CPIN = c_pin if c_pin is not None else C_PIN
        self.VIA_R = dict(VIA_R)
        self.ly = pya.Layout()
        self.ly.read(gds_path)
        self.top = self.ly.top_cell()
        self.dbu = self.ly.dbu
        self.mux = CellGeom("sky130_fd_sc_hd__mux2_1",
                            os.path.join(self.cell_dir, "sky130_fd_sc_hd__mux2_1.gds"),
                            os.path.join(self.cell_dir, "sky130_fd_sc_hd__mux2_1.lef"))
        self.latch = CellGeom("sky130_fd_sc_hd__dlrtp_1",
                              os.path.join(self.cell_dir, "sky130_fd_sc_hd__dlrtp_1.gds"),
                              os.path.join(self.cell_dir, "sky130_fd_sc_hd__dlrtp_1.lef"))

    def rows(self):
        """[(cy, instL, instR), ...] with left/right columns."""
        row_insts = {}
        for inst in self.top.each_inst():
            nm = self.ly.cell(inst.cell_index).name
            if "mux2_1" not in nm:
                continue
            b = inst.bbox()
            cx = (b.left + b.right) / 2.0 * self.dbu
            cy = (b.bottom + b.top) / 2.0 * self.dbu
            row_insts.setdefault(round(cy, 3), []).append((cx, inst))
        centres = sorted(row_insts)
        groups = []
        for cy in centres:
            if groups and cy - groups[-1][0] < 0.5:
                groups[-1][1].extend(row_insts[cy])
            else:
                groups.append([cy, list(row_insts[cy])])
        out = []
        for cy, insts in groups:
            insts.sort(key=lambda t: t[0])
            left = insts[0][1]
            right = insts[1][1] if len(insts) > 1 else None
            out.append((cy, left, right))
        return out

    def latch_inst(self):
        for inst in self.top.each_inst():
            if "dlrtp_1" in self.ly.cell(inst.cell_index).name:
                return inst
        return None

    def access(self, cell, inst, pin):
        return cell.pin_center(pin, inst.trans)

    def run(self, tol_pct):
        rows = self.rows()
        N = len(rows)
        if not N:
            print("ERROR: no mux2_1 instances found in", self.gds_path)
            return 2
        latch = self.latch_inst()
        if latch is None:
            print(f"WARN: no dlrtp_1 latch instance found in {self.gds_path} - "
                  "skipping the terminal top[N]/bot[N] nets")

        # ---------------- conductive universe ----------------
        g = build_graph(self.top, self.ly, self.dbu)
        if not g.p:
            print("ERROR: no metal pieces in macro cell")
            return 2

        def comps_at(x, y):
            """Set of components whose drawn metal overlaps the pin point
            (small tolerance to absorb grid snapping of the pads)."""
            if x is None:
                return set()
            out = set()
            px = (x - 0.06, y - 0.06, x + 0.06, y + 0.06)
            for nid, bx in enumerate(g.box):
                if hit(px, bx):
                    out.add(g.find(nid))
            return out

        # ---- recover nets ----
        nets = {}

        def add(name, cell, inst, pin):
            c = self.access(cell, inst, pin)
            nets.setdefault(name, [])
            if c is None:
                nets[name].append(None)
                return
            cs = comps_at(c[0], c[1])
            if len(cs) == 1:
                nets[name].append(next(iter(cs)))
            elif len(cs) == 0:
                nets[name].append(None)
            else:
                nets[name].append(tuple(sorted(cs)))

        for gi, (cy, l, r) in enumerate(rows):
            if r:
                add(f"ch[{gi}]", self.mux, l, "S")
                add(f"ch[{gi}]", self.mux, r, "S")
        for col in (rows[0][1], rows[0][2]):
            if col:
                add("launch", self.mux, col, "A0")
                add("launch", self.mux, col, "A1")
        for gi in range(N):
            cy, l, r = rows[gi]
            if gi + 1 < N:
                cy1, l1, r1 = rows[gi + 1]
                add(f"top[{gi+1}]", self.mux, l, "X")
                add(f"top[{gi+1}]", self.mux, l1, "A0")
                add(f"top[{gi+1}]", self.mux, r1, "A1")
                add(f"bot[{gi+1}]", self.mux, r, "X")
                add(f"bot[{gi+1}]", self.mux, l1, "A1")
                add(f"bot[{gi+1}]", self.mux, r1, "A0")
            else:
                add(f"top[{N}]", self.mux, l, "X")
                if latch:
                    add(f"top[{N}]", self.latch, latch, "D")
                    add(f"bot[{N}]", self.latch, latch, "GATE")
                add(f"bot[{N}]", self.mux, r, "X")

        # ---- integrity ----
        bad = []
        net_comp = {}
        for nm, comps in nets.items():
            cset = {c for c in comps if c is not None}
            if not cset or len(cset) != 1:
                bad.append((nm, comps))
            else:
                net_comp[nm] = next(iter(cset))

        if bad:
            print("== net integrity ==")
            for nm, comps in sorted(bad):
                print(f"  !! {nm}: members in {len(set(c for c in comps if c is not None))} "
                      f"components - {comps}")
            print("NET INTEGRITY FAIL - cannot trust the delay comparison")
            return 1

        # power components (top rails)
        H = self.top.bbox().top / self.dbu
        vdd = vss = None
        for sem in (MET2, MET1):
            best = None
            for nid, bx in enumerate(g.box):
                if g.lay[nid] != sem or bx[3] < H - 1.5:
                    continue
                w = bx[2] - bx[0]
                if best is None or w > best[0]:
                    best = (w, g.find(nid))
            if best:
                if sem == MET2:
                    vdd = best[1]
                else:
                    vss = best[1]

        comps_of_nets = set(net_comp.values())
        # free metal = non-net non-power components
        free = []
        seen = set()
        for nid in range(len(g.p)):
            if g.lay[nid] not in METALS:
                continue
            c = g.find(nid)
            if c in comps_of_nets or c == vdd or c == vss or c in seen:
                continue
            seen.add(c)
            ba = g.box[nid]
            area = g.area(nid)
            free.append((c, ba, area))

        # ---- stats per net ----
        def stats(c):
            per = {}
            vias = {}
            for nid in range(len(g.p)):
                if g.find(nid) != c:
                    continue
                lyr = g.lay[nid]
                if isinstance(lyr, tuple) and lyr[0] == "CUT":
                    vias[lyr[1]] = vias.get(lyr[1], 0) + 1
                elif lyr in METALS:
                    per[lyr] = per.get(lyr, 0.0) + g.area(nid)
            L = {}
            R = 0.0
            C = 0.0
            for lyr, area in per.items():
                L[lyr] = area / WIRE_W[lyr]
                R += self.RHO[lyr] * L[lyr] / WIRE_W[lyr]
                C += self.CUM * L[lyr]
            for lyr, n in vias.items():
                R += n * self.VIA_R[lyr]
            npin = 0
            for nm, cc in net_comp.items():
                if cc == c:
                    npin += len(nets[nm])
            C += npin * self.CPIN
            return {"R": R, "C": C, "via": vias, "len": L, "tau": 0.5 * R * C}

        st = {}
        def T(nm):
            cc = net_comp[nm]
            if cc not in st:
                st[cc] = stats(cc)
            return st[cc]

        # ---- report ----
        fail = 0
        print("GDS      :", self.gds_path)
        print(f"stages N : {N}")
        print(f"rows     : y = {', '.join(f'{cy:.0f}' for cy, _, _ in rows)}")
        print()
        print("== net integrity ==")
        print(f"  {len(nets)} nets defined, all single-component")
        for nm, comps in sorted(bad):
            print(f"  !! {nm}: {comps}")
        print()
        print("== power isolation ==")
        if vdd is not None:
            print(f"  VDD comp = {vdd}")
        if vss is not None:
            print(f"  VSS comp = {vss}")
        for nm, cc in sorted(net_comp.items()):
            if cc == vdd:
                print(f"  !! {nm} touches VDD"); fail = 1
            if cc == vss:
                print(f"  !! {nm} touches VSS"); fail = 1
        if fail:
            return fail
        if free:
            print(f"  {len(free)} free (un-routed) metal piece(s):")
            for c, b, a in free:
                print(f"    comp {c} @ ({b[0]:.2f},{b[1]:.2f}) area {a:.2f} um2")
                fail = 1

        # ---- per-stage comparison ----
        print()
        print("== per-stage delay index (tau = 0.5*R*C, ps) ==")
        hdr = f"{'stage':<10}{'top tau':>12}{'bot tau':>12}{'diff%':>8}  top/bot L2 L3"
        print(hdr)
        tot_top = tot_bot = 0.0
        # launch
        tt = T("launch")["tau"]
        tot_top += tt; tot_bot += tt
        print(f"{'launch':<10}{tt:>12.2f}{tt:>12.2f}{0:>8}  (shared)")

        for gi in range(1, N + 1):
            tnm = f"top[{gi}]"
            bnm = f"bot[{gi}]"
            if tnm not in net_comp or bnm not in net_comp:
                print(f"{tnm:<10}  MISSING NET")
                fail = 1
                continue
            a = T(tnm)
            b = T(bnm)
            tt = a["tau"]; bt = b["tau"]
            tot_top += tt; tot_bot += bt
            d = (tt - bt) / max(tt, bt, 1e-12) * 100
            if abs(d) > tol_pct:
                fail = 1
            la = a["len"]; lb = b["len"]
            s = (f"{tnm:<10}{tt:>12.2f}{bt:>12.2f}{d:>8.2f}  "
                 f"T:{la.get((69,20),0):.1f}/{la.get((70,20),0):.1f} "
                 f"B:{lb.get((69,20),0):.1f}/{lb.get((70,20),0):.1f}")
            if abs(d) > tol_pct:
                s += "  <-- FAIL"
            print(s)

        # ---- accumulated chains ----
        dchain = (tot_top - tot_bot) / max(tot_top, tot_bot, 1e-12) * 100
        print()
        print("== accumulated chains ==")
        print(f"  top chain tau = {tot_top:.2f} ps  (launch + top[1..{N}])")
        print(f"  bot chain tau = {tot_bot:.2f} ps  (launch + bot[1..{N}])")
        print(f"  difference    = {dchain:.2f} %")
        if abs(dchain) > tol_pct:
            fail = 1
        print()
        if free:
            print("RESULT: FAIL (free metal present)")
        elif fail:
            print(f"RESULT: FAIL (asymmetry > {tol_pct:g} %)")
        else:
            print("RESULT: PASS - the two mux chains are delay-equal "
                  "within tolerance")
        return 1 if fail else 0


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gds", nargs="?", default=os.path.join(here, "arbchain.gds"))
    ap.add_argument("--cell-gds-dir", default=None,
                    help="dir with sky130_fd_sc_hd__mux2_1.gds/dlrtp_1.gds "
                         "(default: beside the gds)")
    ap.add_argument("--cell-lef-dir", default=None,
                    help="dir with mux2_1/dlrtp_1 .lef (default=--cell-gds-dir)")
    ap.add_argument("--tol", type=float, default=1.0,
                    help="max percent diff before FAIL (default 1.0)")
    ap.add_argument("--rho-sheet", default="",
                    help="comma list met1:..,met2:..,met3:..,met4:..")
    ap.add_argument("--rho-via", type=float, default=None)
    ap.add_argument("--c-um", type=float, default=None)
    ap.add_argument("--c-pin", type=float, default=None)
    args = ap.parse_args()

    rho_sheet = dict(RHO_SHEET)
    if args.rho_sheet:
        for tok in args.rho_sheet.split(","):
            k, v = [x.strip() for x in tok.split(":")]
            L = {1: MET1, 2: MET2, 3: MET3, 4: MET4}[int(k[-1])]
            rho_sheet[L] = float(v)
    rho_via = args.rho_via if args.rho_via is not None else RHO_VIA
    c_um = args.c_um if args.c_um is not None else C_UM
    c_pin = args.c_pin if args.c_pin is not None else C_PIN

    ck = ArbChecker(args.gds, args.cell_gds_dir, args.cell_lef_dir,
                    rho_sheet=rho_sheet, rho_via=rho_via,
                    c_um=c_um, c_pin=c_pin)
    sys.exit(ck.run(args.tol))


if __name__ == "__main__":
    main()