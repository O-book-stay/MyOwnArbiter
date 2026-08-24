#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# gen_arbchain.py  (R3: short-free revision)
#
# R3 修复“同层信号短路”的根源：
# [R3-1] PITCH 3.40 -> 4.60。原来旋转后的 bottom mux 高 4.14 > 3.40，
#        相邻行 cell 重叠、bottom 引脚侵入下一行通道区，是短路的根源。
# [R3-2] 每个信号网一条 *专用* met2 水平通道（放在行间 gap 中）：
#        net bot[g+1] @ row_g + 3.20 , net top[g+1] @ row_g + 3.70 ,
#        net ch[g]    @ row_g + 1.80（行内，S 引脚上方）。
#        通道之间、通道与 pad 之间全部 >= 0.14 (m2.2) / 0.30 (m3.3)。
# [R3-3] 任何需要跨越 *别人* met2 通道的连接（A1(top), A0(bot), 两个 X，
#        以及运行时检测到冲突的 stub）都改成 via2 + met3 riser：
#        met3 垂直越过 met2 通道不构成短路。
# [R3-4] 电源：met1 strap 放在两列 mux 之间的净空走廊 (x=4.90/5.90)，
#        每行的 met2 电源横线只走 y=0.065 / 2.65（rail y），x 从 3.40
#        到 bottom mux 竖直 rail，绝不横穿任何信号通道。
# [R3-5] launch 走 met3（y=0.60 水平线 + met4 底部 pad），位置在所有
#        met3 riser 起点之下，不再与 X riser 相撞。
# [R3-6] 运行时冲突检测：每个 stub/riser/竖线先对本层已画图形做
#        间距检查，冲突则自动 jog（±0.65/±1.30）；布完后全图 pairwise
#        间距预检并打印 warning。
# [R3-7] q 输出补上真正的 via3/met4；删除 R2 里悬空的 via3/met4 pad。
# [R3-8] prBoundary 保持 (235,4)。
# ============================================================

import argparse, os, re, sys, json, math, urllib.request
import klayout.db as pya

CELL_FILES = {
    "sky130_fd_sc_hd__mux2_1.gds": "cells/mux2/sky130_fd_sc_hd__mux2_1.gds",
    "sky130_fd_sc_hd__mux2_1.lef": "cells/mux2/sky130_fd_sc_hd__mux2_1.lef",
    "sky130_fd_sc_hd__dlrtp_1.gds": "cells/dlrtp/sky130_fd_sc_hd__dlrtp_1.gds",
    "sky130_fd_sc_hd__dlrtp_1.lef": "cells/dlrtp/sky130_fd_sc_hd__dlrtp_1.lef",
}
CELL_BASE = ("https://raw.githubusercontent.com/google/"
             "skywater-pdk-libs-sky130_fd_sc_hd/main/")

def ensure_cells(gds_dir, lef_dir):
    import shutil, subprocess, tempfile
    for d in (gds_dir, lef_dir):
        if d and os.path.exists(os.path.join(d, "sky130_fd_sc_hd__mux2_1.gds")):
            return gds_dir, lef_dir
    tmp = tempfile.mkdtemp(prefix="arbchain_cells_")
    for fname, path in CELL_FILES.items():
        url = CELL_BASE + path; dst = os.path.join(tmp, fname)
        try:
            if shutil.which("curl"):
                subprocess.check_call(["curl","-fsSL","-o",dst,url],
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
            else:
                urllib.request.urlretrieve(url, dst)
        except Exception as e:
            sys.exit(f"failed to fetch {url}: {e}")
    return tmp, tmp

class _UF:
    def __init__(self): self.nodes=[]
    def find(self,x):
        while self.nodes[x]!=x:
            self.nodes[x]=self.nodes[self.nodes[x]]; x=self.nodes[x]
        return x
    def union(self,a,b):
        ra,rb=self.find(a),self.find(b)
        if ra!=rb: self.nodes[rb]=ra

# ---------------- geometry / technology ----------------
STAGES=16; MUX_W,MUX_H=4.14,2.72; LATCH_W,LATCH_H=5.98,2.72
PITCH=4.60                       # [R3-1] was 3.40 (< rotated cell height 4.14)
GAP=1.5; CH=2*GAP; W=2*(GAP+MUX_W); XC=W/2; YOFF=0.24
H=(STAGES+1)*PITCH+2*YOFF
MUX_LEF="sky130_fd_sc_hd__mux2_1"; LATCH_LEF="sky130_fd_sc_hd__dlrtp_1"

GRID=0.005
LAY_LI1 =(67,20); LAY_MET1=(68,20); LAY_MET2=(69,20)
LAY_MET3=(70,20); LAY_MET4=(71,20)
LAY_MCON=(67,44); LAY_VIA1=(68,44); LAY_VIA2=(69,44); LAY_VIA3=(70,44)
LAY_PR =(235,4)                  # [R3-8]

# [R3-2] dedicated channel offsets (relative to row origin y0 = g*PITCH+YOFF)
# [R4-1] heights SWAPPED vs R3: bot-net rides the UPPER gap line, top-net the
#        LOWER one.  Verified per tap this gives every chain the same via
#        stack per stage: X entry via1-only, one A drop via1-only, one A drop
#        via1+via2 (the met3 hop).  With the old assignment the bot chain got
#        two hops per stage while the top chain got one.
CH_CH =1.595    # net ch[g]    : S(top g) + S(bot g)          (met2, in-row)
                #   1.80 collided with the X pin pad (bottom 2.06):
                #   X pad [2.06,2.38] vs ch band y+0.085 -> need y+0.085<=1.92
CH_BOT=3.80     # net bot[g+1] : A1(top g+1)+A0(bot g+1)+X(bot g)  (met2, HIGH)
                #   >= ct+0.41: the LOW line carries 0.37-tall landing pads,
                #   their tops need 0.14 to the HIGH line's bottom edge
CH_TOP=3.35     # net top[g+1] : A0(top g+1)+A1(bot g+1)+X(top g)  (met2, LOW)
                #   >=3.345: the VDD stitch pad at (3.70, y+2.96) is 0.32
                #   tall -> its top edge 3.12 needs 0.14 to the channel

# [R3-4] power: straps in the clear corridor between the two mux columns
STRAP_VSS=4.90; STRAP_VDD=5.90
RAIL_X0=3.40                    # met2 power line start x (right of left-col pins)
PW_VIA_X=3.70                   # via1 x onto the top-mux horizontal rails
BOT_VPW_X=8.625                 # centre of bottom-mux vertical VPWR rail (W-2.655)
BOT_VGN_X=11.215                # centre of bottom-mux vertical VGND rail (W-0.065)

LAUNCH_X=5.00; LAUNCH_Y=0.60    # [R3-5] met3 launch line y (below every riser)

MACRO_X,MACRO_Y=83.30,7.20
CORR_W=6.00; TW=W+CORR_W
VP_RAIL=(H-1.40,H-0.70)         # met2 VPWR top rail
VG_RAIL=(H-0.68,H-0.01)         # met1 VGND top rail
VG_RAIL_X0=12.00

# exact via sizes + pad rectangles (dx,dy) -- unchanged from R2
MCON=0.17; V1=0.15; V2=0.20; V3=0.20
M1P_V1 =(0.26,0.32)
M2P_V1 =(0.26,0.32)
M2P_V2 =(0.28,0.37)
M3P_V2 =(0.34,0.34)
M3P_V3 =(0.38,0.38)
M4P_V3 =(0.34,0.34)
W_M3,W_M4=0.30,0.30

# same-layer spacing margins used by the runtime conflict checker
SPACING={(68,20):0.14,(69,20):0.14,(70,20):0.30,(71,20):0.30}

def snap(v): return round(v/GRID)*GRID
def pt(x,y): return (round(snap(x)*1000), round(snap(y)*1000))

class Cell:
    def __init__(self,name,gds_path,lef_path):
        self.name=name; self.gds_path=gds_path; self.lef_path=lef_path
        self.pins={}; self._parse_lef(); self._load_gds()
    def _parse_lef(self):
        cur=None; self.size=(0.0,0.0)
        for line in open(self.lef_path):
            if re.match(r"\s*(OBS|END)\b",line): cur=None; continue
            m=re.search(r"PIN\s+(\S+)",line)
            if m: cur=m.group(1); self.pins.setdefault(cur,[])
            m=re.search(r"LAYER\s+(\S+)\s*;",line)
            if m and cur: self._layer=m.group(1)
            m=re.match(r"\s*SIZE\s+([\d.\-]+)\s+BY\s+([\d.\-]+)\s*;",line)
            if m: self.size=(float(m.group(1)),float(m.group(2)))
            m=re.match(r"\s*RECT\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*;",line)
            if m and cur:
                r=[float(m.group(i)) for i in range(1,5)]
                self.pins[cur].append((self._layer,tuple(r)))
    def _load_gds(self):
        self.ly=pya.Layout(); self.ly.read(self.gds_path)
        self.cell=self.ly.cell(self.name)
        if self.cell is None: sys.exit(f"cell {self.name} not found")
        self.dbu=self.ly.dbu; self._build_pin_metal()
    def _region(self,ln,dt):
        r=pya.Region(); it=self.cell.begin_shapes_rec(self.ly.layer(ln,dt))
        while not it.at_end():
            r.insert(it.shape().bbox().transformed(it.trans())); it.next()
        return r.merged()
    def _build_pin_metal(self):
        metals={"li1":self._region(67,20),"met1":self._region(68,20),
                "met2":self._region(69,20),"met3":self._region(70,20)}
        cuts={"via":self._region(67,44),"via2":self._region(68,44),
              "via3":self._region(69,44)}
        polys={}; uf=_UF(); nid=0
        for name,reg in metals.items():
            polys[name]=[]
            for po in reg.each():
                polys[name].append((nid,po)); uf.nodes.append(nid); nid+=1
        for cn,la,lb in [("via","li1","met1"),("via2","met1","met2"),
                         ("via3","met2","met3")]:
            for cp in cuts[cn].each():
                ids=[]; creg=pya.Region(cp)
                for i,p in polys[la]:
                    if not (pya.Region(p)&creg).is_empty(): ids.append(i)
                for i,p in polys[lb]:
                    if not (pya.Region(p)&creg).is_empty(): ids.append(i)
                if ids:
                    for i in ids[1:]: uf.union(ids[0],i)
        self.pin_metal={}
        for pin in self.pins:
            comps=set()
            for layer,r in self.pins[pin]:
                if layer!="li1": continue
                cx=int(((r[0]+r[2])/2)/self.dbu); cy=int(((r[1]+r[3])/2)/self.dbu)
                p=pya.Point(cx,cy)
                for i,po in polys["li1"]:
                    if po.inside(p): comps.add(uf.find(i)); break
            reg=pya.Region()
            for name in metals:
                for i,po in polys[name]:
                    if uf.find(i) in comps: reg.insert(po)
            reg.merge(); self.pin_metal[pin]=reg
    def li_pin_center(self,pin,trans):
        dbu=self.dbu; best=None; best_a=0
        li1=self._region(67,20).transformed(trans)
        for layer,r in self.pins.get(pin,[]):
            if layer!="li1": continue
            rb=pya.Box(round(r[0]/dbu),round(r[1]/dbu),
                       round(r[2]/dbu),round(r[3]/dbu)).transformed(trans)
            inter=(pya.Region(rb)&li1).merged()
            for po in inter.each():
                a=po.area()
                if a>best_a: best_a=a; best=po.bbox()
        if best is None: return None
        return (((best.left+best.right)/2)*dbu, ((best.bottom+best.top)/2)*dbu)

    # ---------- [R4-2] mcon-clearance aware access selection ----------
    _acc_memo = {}
    def mcon_boxes(self, trans):
        """every mcon inside this placed cell (macro coords)."""
        mc = pya.Region()
        it = self.cell.begin_shapes_rec(self.ly.layer(67, 44))
        while not it.at_end():
            mc.insert(it.shape().bbox().transformed(it.trans()))
            it.next()
        return mc.transformed(trans).merged()

    def _find_clear_access(self, pin, trans, need=0.20):
        """snapped mcon centre on one of the pin's li pieces (mcon fully
        covered by li), keeping >=need from every cell-internal mcon.
        Pieces are tried largest-first and each piece's own centre is
        preferred, so taps stay on their designed li centres unless that
        spot genuinely conflicts (fixes ct.2: the S top-bar centre sat
        0.17 under the cell's VPWR-rail mcons -> moves to the S vertical
        side branch, which has >=0.34 of room)."""
        dbu = self.dbu
        li1 = self._region(67, 20).transformed(trans)
        boxes = [mb.bbox() for mb in self.mcon_boxes(trans).each()]

        def dist(pb, mb):
            gx = max(pb.left - mb.right, mb.left - pb.right, 0)
            gy = max(pb.bottom - mb.top, mb.bottom - pb.top, 0)
            return math.hypot(gx, gy) * dbu

        h = int(MCON / 2 / dbu)
        g5 = 5                                    # manufacturing grid, dbu
        pieces = []
        for layer, r in self.pins.get(pin, []):
            if layer != "li1":
                continue
            rb = pya.Box(round(r[0] / dbu), round(r[1] / dbu),
                         round(r[2] / dbu), round(r[3] / dbu)).transformed(trans)
            for po in (pya.Region(rb) & li1).merged().each():
                bb = po.bbox()
                ix0, ix1 = bb.left + h, bb.right - h
                iy0, iy1 = bb.bottom + h, bb.top - h
                ix0 = -((-ix0) // g5) * g5; ix1 = (ix1 // g5) * g5
                iy0 = -((-iy0) // g5) * g5; iy1 = (iy1 // g5) * g5
                if ix0 <= ix1 and iy0 <= iy1:
                    pieces.append((po.area(), bb, ix0, ix1, iy0, iy1))
        if not pieces:
            sys.exit(f"no li room for an mcon on pin {pin}")
        pieces.sort(key=lambda p: -p[0])

        fb = None                                 # (dmin, x, y)
        for area, bb, ix0, ix1, iy0, iy1 in pieces:
            cx, cy = (ix0 + ix1) // 2, (iy0 + iy1) // 2
            pb = pya.Box(cx - h, cy - h, cx + h, cy + h)
            d0 = min([dist(pb, mb) for mb in boxes] or [9.0])
            if d0 >= need:
                return (cx * dbu, cy * dbu)       # designed centre is legal
            if fb is None or d0 > fb[0]:
                fb = (d0, cx, cy)
            for x in range(ix0, ix1 + 1, g5):
                for y in range(iy0, iy1 + 1, g5):
                    if x == cx and y == cy:
                        continue
                    pb = pya.Box(x - h, y - h, x + h, y + h)
                    dmin = min([dist(pb, mb) for mb in boxes] or [9.0])
                    if dmin >= need:
                        return (x * dbu, y * dbu)
                    if dmin > fb[0]:
                        fb = (dmin, x, y)
        print(f"WARN: access {pin}: best mcon clearance {fb[0]:.3f}um "
              f"< {need}um")
        return (fb[1] * dbu, fb[2] * dbu)

    def clear_access(self, pin, kind, y0):
        """tapped point (x,y) for `pin` in row/frame `kind`
        ('t' mux top row, 'b' mux bottom row, 'L' latch), computed once per
        (pin, frame) and reused for every row."""
        key = (self.name, pin, kind)
        if key not in Cell._acc_memo:
            if kind == "b":
                t = (pya.Trans(0, False, round(W * 1000), round(YOFF * 1000)) *
                     pya.Trans.M90)
                oy = YOFF
                oxf = W
            elif kind == "L":
                t = pya.Trans(0, False,
                              round(((W - LATCH_W) / 2) * 1000), 0)
                oy = 0.0
                oxf = (W - LATCH_W) / 2
            else:
                t = pya.Trans(0, False, 0, round(YOFF * 1000))
                oy = YOFF
                oxf = 0.0
            p = self._find_clear_access(pin, t)
            Cell._acc_memo[key] = (p[0] - oxf, p[1] - oy)
        lx, ly = Cell._acc_memo[key]
        ox = W if kind == "b" else (((W - LATCH_W) / 2) if kind == "L" else 0.0)
        return (snap(ox + lx), snap(y0 + ly))

    def access_point(self, kind, g, pin):
        return self.clear_access(pin, kind, g * PITCH + YOFF)

class Draw:
    def __init__(self,ly,top):
        self.ly=ly; self.top=top; self.layers={}; self.shapes=[]; self.uf=[]
    def _find(self,x):
        p=self.uf
        while p[x]!=x:
            p[x]=p[p[x]]; x=p[x]
        return x
    def l(self,layer):
        if layer not in self.layers:
            self.layers[layer]=self.ly.layer(layer[0],layer[1])
        return self.layers[layer]
    def box(self,layer,x1,y1,x2,y2):
        p1=pt(x1,y1); p2=pt(x2,y2)
        self.top.shapes(self.l(layer)).insert(pya.Box(p1[0],p1[1],p2[0],p2[1]))
        self.shapes.append((layer,(x1,y1,x2,y2)))
        idx=len(self.shapes)-1; self.uf.append(idx)
        b=self.shapes[idx][1]
        for j in range(idx):                    # same-layer touch => same net
            l2,b2=self.shapes[j]
            if l2!=layer: continue
            if (max(b2[0]-b[2], b[0]-b2[2], 0.0)==0.0 and
                max(b2[1]-b[3], b[1]-b2[3], 0.0)==0.0):
                ra,rb=self._find(j),self._find(idx)
                if ra!=rb: self.uf[max(ra,rb)]=min(ra,rb)
    def h(self,layer,y,x0,x1,w):
        self.box(layer,x0,y-w/2,x1,y+w/2)
    def v(self,layer,x,y0,y1,w):
        self.box(layer,x-w/2,y0,x+w/2,y1)
    # ---------- [R3-6] runtime conflict checking ----------
    def clear(self,layer,x1,y1,x2,y2,margin):
        """True if the given rect keeps `margin` from every already-drawn
        shape on the same layer (touching/overlapping = same-net merge, ok)."""
        for (lay,b) in self.shapes:
            if lay!=layer: continue
            dx=max(b[0]-(x2+margin), x1-margin-b[2], 0.0)   # >=0 -> disjoint
            dy=max(b[1]-(y2+margin), y1-margin-b[3], 0.0)
            if dx==0.0 and dy==0.0:
                # disjoint neither in x nor y AND separated -> gap < margin?
                gx=max(b[0]-x2, x1-b[2], 0.0)
                gy=max(b[1]-y2, y1-b[3], 0.0)
                if gx==0.0 and gy==0.0:  continue   # overlaps/abuts: merge
                if gx<margin and gy<margin: return False
        return True

def top_trans(g):
    return pya.Trans(0,False,0,round((g*PITCH+YOFF)*1000))
def bot_trans(g):
    return (pya.Trans(0,False,round(W*1000),round((g*PITCH+YOFF)*1000))*
            pya.Trans.M90)
def latch_trans(y):
    return pya.Trans(0,False,round(((W-LATCH_W)/2)*1000),round(y*1000))

# ============================================================
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cell-gds-dir"); ap.add_argument("--cell-lef-dir")
    ap.add_argument("--out",default=os.path.dirname(os.path.abspath(__file__)))
    args=ap.parse_args()
    def default_dir(sub):
        pdk=os.environ.get("PDK_ROOT","")
        return os.path.join(pdk,"sky130A","libs.ref","sky130_fd_sc_hd",sub)
    gds_dir=args.cell_gds_dir or default_dir("gds")
    lef_dir=args.cell_lef_dir or default_dir("lef")
    gds_dir,lef_dir=ensure_cells(gds_dir,lef_dir)

    mux=Cell(MUX_LEF,os.path.join(gds_dir,"sky130_fd_sc_hd__mux2_1.gds"),
             os.path.join(lef_dir,"sky130_fd_sc_hd__mux2_1.lef"))
    latch=Cell(LATCH_LEF,os.path.join(gds_dir,"sky130_fd_sc_hd__dlrtp_1.gds"),
               os.path.join(lef_dir,"sky130_fd_sc_hd__dlrtp_1.lef"))

    ly=pya.Layout(); ly.dbu=0.001
    macro=ly.create_cell("arbchain"); d=Draw(ly,macro)
    ly.read(mux.gds_path); ly.read(latch.gds_path)
    mux_ref=ly.cell(mux.name); latch_ref=ly.cell(latch.name)
    ly_r=STAGES*PITCH+YOFF                       # latch row origin (=MUX_TOP)
    MUX_TOP=ly_r                                 # top of the last mux row
    for g in range(STAGES):
        macro.insert(pya.CellInstArray(mux_ref,top_trans(g)))
        macro.insert(pya.CellInstArray(mux_ref,bot_trans(g)))
    macro.insert(pya.CellInstArray(latch_ref,latch_trans(ly_r)))

    WARN=[]
    def warn(msg): WARN.append(msg)

    # ---------- [R4] primitives ----------
    def rect_c(layer,dx,dy,x,y):
        d.box(layer,x-dx/2,y-dy/2,x+dx/2,y+dy/2)

    def acc(cell,kind,g,pin):
        y0 = ly_r if kind=="L" else g*PITCH+YOFF
        return cell.clear_access(pin,kind,y0)

    def pin_stack(cell,kind,g,pin):
        """via1-only tap: li -> mcon -> m1 pad -> via1 -> m2 pad."""
        c=acc(cell,kind,g,pin)
        d.box(LAY_MCON,c[0]-MCON/2,c[1]-MCON/2,c[0]+MCON/2,c[1]+MCON/2)
        rect_c(LAY_MET1,*M1P_V1,*c); rect_c(LAY_MET2,*M2P_V1,*c)
        d.box(LAY_VIA1,c[0]-V1/2,c[1]-V1/2,c[0]+V1/2,c[1]+V1/2)
        return c

    def stub(c,ch_y):
        """pure-met2 run tap->channel; overshoots past the far edge of the
        line so the junction cannot form a sub-minimum notch."""
        ya,yb=min(c[1],ch_y),max(c[1],ch_y)
        if ch_y>c[1]: yb+=0.085
        else:         ya-=0.085
        d.v(LAY_MET2,c[0],ya,yb,0.17)

    def riser(c,ch_y,jog,tag="",land=True):
        """met3 hop for taps whose straight run would cross foreign met2.
        jog!=0: pin(via1 stack) -> met2 drop -> met2 jog -> via2/m3 pad ->
        met3 run -> via2/m2 landing pad.  via2 never sits at the pin row
        (neighbour taps 0.40 away: 0.28/0.34 pads there break m2.2/m3.2).
        jog==0 (isolated column): classic straight riser with the via2/m3
        pad right at the pin - legal since no neighbour pin is close."""
        if jog==0.0:
            yy=snap(ch_y)
            rect_c(LAY_MET2,*M2P_V2,*c)
            d.box(LAY_VIA2,c[0]-V2/2,c[1]-V2/2,c[0]+V2/2,c[1]+V2/2)
            rect_c(LAY_MET3,*M3P_V2,*c)
            d.v(LAY_MET3,c[0],min(c[1],yy),max(c[1],yy),W_M3)
            if land:
                rect_c(LAY_MET2,*M2P_V2,c[0],yy)
                d.box(LAY_VIA2,c[0]-V2/2,yy-V2/2,c[0]+V2/2,yy+V2/2)
                rect_c(LAY_MET3,*M3P_V2,c[0],yy)
            return c[0]
        up=ch_y>c[1]
        off=0.45 if up else 0.40
        jy=c[1]+(off if up else -off)
        jy=snap(min(jy,ch_y-0.32) if up else max(jy,ch_y+0.32))
        d.v(LAY_MET2,c[0],min(c[1],jy),max(c[1],jy),0.17)
        xx=snap(c[0]+jog)
        if xx!=c[0]:
            d.h(LAY_MET2,jy,min(c[0],xx),max(c[0],xx),0.17)
        rect_c(LAY_MET2,*M2P_V2,xx,jy)
        d.box(LAY_VIA2,xx-V2/2,jy-V2/2,xx+V2/2,jy+V2/2)
        rect_c(LAY_MET3,*M3P_V2,xx,jy)
        d.v(LAY_MET3,xx,min(jy,ch_y),max(jy,ch_y),W_M3)
        if land:
            yy=snap(ch_y)
            rect_c(LAY_MET2,*M2P_V2,xx,yy)
            d.box(LAY_VIA2,xx-V2/2,yy-V2/2,xx+V2/2,yy+V2/2)
            rect_c(LAY_MET3,*M3P_V2,xx,yy)
        return xx

    def channel(y,xs):
        """met2 channel across its members, extended half a stub width plus
        pad overhang past the outermost taps (a line-end must never land
        inside a stub or landing-pad footprint)."""
        x0=max(0.0,snap(min(xs)-0.17)); x1=snap(max(xs)+0.17)
        d.h(LAY_MET2,y,x0,x1,0.17)

    # ---------- ch[g] : both S taps -> in-row met2 line ----------
    for g in range(STAGES):
        y0=g*PITCH+YOFF; cy=snap(y0+CH_CH)
        s_t=pin_stack(mux,"t",g,"S"); s_b=pin_stack(mux,"b",g,"S")
        stub(s_t,cy); stub(s_b,cy)
        channel(cy,[0.0,s_t[0],s_b[0]])

    # ---------- stage-0 launch seeding ----------
    xc=snap(LAUNCH_X)
    lxs=[]
    for kind,pin,jog in (("t","A0",-0.65),("t","A1",+0.65),
                         ("b","A1",-0.65),("b","A0",+0.65)):
        c=pin_stack(mux,kind,0,pin)
        lxs.append(riser(c,LAUNCH_Y,jog,tag=f"L{kind}{pin}",land=False))
    if lxs:
        d.h(LAY_MET3,LAUNCH_Y,min(lxs)-0.17,max(lxs)+0.17,W_M3)
        d.v(LAY_MET3,xc,0.45,LAUNCH_Y,W_M3)
        rect_c(LAY_MET3,*M3P_V3,xc,0.45)
        d.box(LAY_VIA3,xc-V3/2,0.45-V3/2,xc+V3/2,0.45+V3/2)
        rect_c(LAY_MET4,*M4P_V3,xc,0.45)
        d.v(LAY_MET4,xc,0.0,0.45,W_M4)
        d.box(LAY_MET4,xc-0.17,0,xc+0.17,0.72)      # [fix m4.4] area 0.245

    # ---------- gaps 1..15 : bot[g] on the HIGH line, top[g] on the LOW line.
    # Natural result of [R4-1]: each chain = two via1 stubs + one met3 riser.
    #   top[g] (LOW) : xt/a0t stubs, a1b riser (hops the cb line), jog left
    #   bot[g] (HIGH): xb/a1t stubs, a0b riser (hops the VSS line), jog right
    for g in range(1,STAGES):
        y0=(g-1)*PITCH+YOFF
        cb=snap(y0+CH_BOT); ct=snap(y0+CH_TOP)
        a1t=pin_stack(mux,"t",g,"A1"); a0b=pin_stack(mux,"b",g,"A0")
        a0t=pin_stack(mux,"t",g,"A0"); a1b=pin_stack(mux,"b",g,"A1")
        xt =pin_stack(mux,"t",g-1,"X"); xb =pin_stack(mux,"b",g-1,"X")
        channel(cb,[a1t[0]+0.65,a0b[0]+0.65,xb[0]])
        channel(ct,[xt[0],a0t[0],a1b[0]-0.65])
        stub(xt,ct); stub(a0t,ct); stub(a1t,cb); stub(xb,cb)
        riser(a1b,ct,-0.65,tag=f"a1b{g}")   # hops the bot[g] line
        riser(a0b,cb,+0.65,tag=f"a0b{g}")   # hops the per-row VSS line

    # ---------- latch : nets top[16] / bot[16] live in gap 15 ----------
    ylat=ly_r; y15=(STAGES-1)*PITCH+YOFF
    cb=snap(y15+CH_BOT); ct=snap(y15+CH_TOP)
    xt=pin_stack(mux,"t",STAGES-1,"X")
    xb=pin_stack(mux,"b",STAGES-1,"X")
    dp=pin_stack(latch,"L",0,"D")       # D  <- top[16]
    gp=pin_stack(latch,"L",0,"GATE")    # GATE <- bot[16]
    channel(ct,[xt[0],dp[0]+0.65])
    channel(cb,[gp[0]-0.65,xb[0]])
    stub(xt,ct); stub(xb,cb)
    riser(dp,ct,+0.65,tag="D")          # hops the bot[16] line
    riser(gp,cb,-0.65,tag="GATE")       # parity riser for the bot chain

    # q / arb_rst_n on met3 tracks above the latch [R3-7]
    # [fix via2.2] tracks moved so a riser's two via2s stay >=0.40 apart
    q_track=snap(ylat+2.95); rst_track=snap(ylat+3.10)
    qp=pin_stack(latch,"L",0,"Q")
    if qp:
        riser(qp,q_track,0.0,tag="Q")
        d.h(LAY_MET3,q_track,qp[0]-0.17,TW,W_M3)
        rect_c(LAY_MET3,*M3P_V3,TW-0.34,q_track)
        d.box(LAY_VIA3,TW-0.34-V3/2,q_track-V3/2,TW-0.34+V3/2,q_track+V3/2)
        rect_c(LAY_MET4,*M4P_V3,TW-0.34,q_track)
    rp=pin_stack(latch,"L",0,"RESET_B")
    if rp:
        riser(rp,rst_track,0.0,tag="RST")
        d.h(LAY_MET3,rst_track,0.0,rp[0]+0.17,W_M3)

    # ---------- [R3-4] power ----------
    def rail_bands(cell,tr,pin):
        out=set()
        dy = tr.disp.y * cell.dbu
        for layer,r in cell.pins.get(pin,[]):
            if layer=="met1" and (r[2]-r[0])>=MUX_W-0.01:
                out.add((round(r[1]+dy,3), round(r[3]+dy,3)))
        return out

    def v1_at(x,y):
        rect_c(LAY_MET1,*M1P_V1,x,y); rect_c(LAY_MET2,*M2P_V1,x,y)
        d.box(LAY_VIA1,x-V1/2,y-V1/2,x+V1/2,y+V1/2)

    # straps in the clear corridor (they touch no cell metal except where
    # explicitly stitched below)
    d.v(LAY_MET1,STRAP_VSS,0.0,MUX_TOP-0.10,0.17)
    d.v(LAY_MET1,STRAP_VDD,0.0,MUX_TOP-0.10,0.17)

    # per mux row: two met2 lines at the top-mux rail y, x in [3.40, rail-x]
    for g in range(STAGES):
        t=top_trans(g)
        bands={}
        for net,pin in (("VDD","VPWR"),("VSS","VGND")):
            for y0,y1 in rail_bands(mux,t,pin):
                bands.setdefault(net,set()).add(snap((y0+y1)/2))
        for net,ym in bands.items():
            for ym in bands[net]:
                end = BOT_VPW_X if net=="VDD" else BOT_VGN_X
                strap = STRAP_VDD if net=="VDD" else STRAP_VSS
                d.h(LAY_MET2,ym,RAIL_X0,end,0.17)
                v1_at(PW_VIA_X,ym)      # onto the top-mux horizontal rail
                v1_at(strap,ym)         # onto the met1 strap
                v1_at(end,ym)           # onto the bottom-mux vertical rail

    # latch power: lower rail touched directly by its strap, upper rail via a
    # met2 jumper + met2 drop to the other strap
    lb={}
    for pin in ("VPWR","VGND"):
        for y0,y1 in rail_bands(latch,latch_trans(ylat),pin):
            lb.setdefault(pin,set()).add((y0,y1))
    lows=[]
    for pin,ys in lb.items():
        for y0,y1 in ys: lows.append((y0,y1,pin))
    lows.sort()
    if lows:
        y0,y1,low_pin=lows[0]
        low_net="VDD" if low_pin=="VPWR" else "VSS"
        low_strap = STRAP_VDD if low_net=="VDD" else STRAP_VSS
        d.v(LAY_MET1,low_strap,0.0,snap((y0+y1)/2),0.17)   # direct, same net
        hi_pin = "VGND" if low_pin=="VPWR" else "VPWR"
        hi_net = "VSS" if hi_pin=="VGND" else "VDD"
        hi_strap = STRAP_VSS if hi_net=="VSS" else STRAP_VDD
        for yy0,yy1 in lb.get(hi_pin,()):
            ym=snap((yy0+yy1)/2)
            d.h(LAY_MET2,ym,4.20,hi_strap,0.17)
            v1_at(4.60,ym)                                 # onto latch rail
            v1_at(hi_strap,snap(MUX_TOP-0.14))             # onto strap top
            d.v(LAY_MET2,hi_strap,snap(MUX_TOP-0.14),ym,0.17)

    # top-level VPWR (met2) / VGND (met1) rails [R3-4]
    vpm=(VP_RAIL[0]+VP_RAIL[1])/2
    d.box(LAY_MET2,0,VP_RAIL[0],14.95,VP_RAIL[1])
    d.v(LAY_MET2,STRAP_VDD,MUX_TOP-0.14,vpm,0.17)
    v1_at(STRAP_VDD,snap(MUX_TOP-0.14))
    d.box(LAY_MET1,VG_RAIL_X0,VG_RAIL[0],TW,VG_RAIL[1])
    vgm=(VG_RAIL[0]+VG_RAIL[1])/2
    # [fix m2.1] the jumper crosses the VGND line fully instead of stopping
    # on its centreline (that left a 0.085 notch at the T corner)
    d.v(LAY_MET2,15.40,snap(MUX_TOP+0.06),vgm+0.085,0.17)
    d.h(LAY_MET2,vgm,15.315,TW-0.28,0.17)
    v1_at(16.40,vgm)

    d.box(LAY_PR,0,0,TW,H)
    d.box((236,0),0,0,TW,H)

    # ---------- [R4-5] whole-figure spacing preview ----------
    def preview():
        idxs=[i for i,(l,b) in enumerate(d.shapes) if l in SPACING]
        n=len(idxs)
        for i in range(n):
            i0=idxs[i]; l1,b1=d.shapes[i0]
            for j in range(i+1,n):
                j0=idxs[j]; l2,b2=d.shapes[j0]
                if l1!=l2: continue
                gx=max(b1[0]-b2[2], b2[0]-b1[2], 0.0)
                gy=max(b1[1]-b2[3], b2[1]-b1[3], 0.0)
                if gx==0.0 and gy==0.0:
                    continue                     # touch/overlap
                if d._find(i0)==d._find(j0):
                    continue                     # same net chain
                dd=math.hypot(gx,gy)             # edge-parallel OR corner gap
                if dd<SPACING[l1]-1e-9:
                    warn(f"spacing {l1}: {b1} vs {b2} (gap {dd:.3f})")
    preview()
    for w in WARN: print("WARN:",w)

    out_dir=args.out; os.makedirs(out_dir,exist_ok=True)
    gds=os.path.join(out_dir,"arbchain.gds"); ly.write(gds); print("wrote",gds)
    with open(os.path.join(out_dir,"arbchain_routing.json"),"w") as fh:
        json.dump([{"layer":list(l),"box":[round(v,3) for v in b]}
                   for l,b in d.shapes],fh)

    pin_coords={"q_y":q_track,"rst_y":rst_track,
                "launch_x":xc,"launch_y":0.70}
    emit_artifacts(out_dir,pin_coords)

# ============================================================
def emit_artifacts(out_dir,pc):
    name="arbchain"; lat=STAGES*PITCH+YOFF
    def ch_y(g): return g*PITCH+YOFF+CH_CH
    def pr(l,x1,y1,x2,y2): return (l,(x1,y1,x2,y2))
    pins=[]
    for g in range(STAGES):
        pins.append((f"ch[{g}]","INPUT","SIGNAL",
                     [pr("met2",0.0,ch_y(g)-0.15,0.30,ch_y(g)+0.15)]))
    xsp=pc["launch_x"]
    pins.append(("launch","INPUT","SIGNAL",
                 [pr("met4",xsp-0.17,0.0,xsp+0.17,0.72)]))
    pins.append(("arb_rst_n","INPUT","SIGNAL",
                 [pr("met3",0.0,pc["rst_y"]-0.15,0.30,pc["rst_y"]+0.15)]))
    pins.append(("q","OUTPUT","SIGNAL",
                 [pr("met3",TW-0.68,pc["q_y"]-0.15,TW,pc["q_y"]+0.15)]))
    pins.append(("VPWR","INOUT","POWER",
                 [pr("met2",13.20,VP_RAIL[0],14.95,VP_RAIL[1])]))
    pins.append(("VGND","INOUT","GROUND",
                 [pr("met1",VG_RAIL_X0,VG_RAIL[0],TW,VG_RAIL[1])]))

    L=["# LEF abstract","VERSION 5.8 ;",'BUSBITCHARS "[]" ;','DIVIDERCHAR "/" ;',
       f"MACRO {name}"," CLASS BLOCK ;"," ORIGIN 0 0 ;",
       f" SIZE {TW:.3f} BY {H:.3f} ;"," SYMMETRY X Y ;"]
    for p,dirn,use,rects in pins:
        L+=[f" PIN {p}",f" DIRECTION {dirn} ;",f" USE {use} ;"]
        for l,r in rects:
            L+=[" PORT",f" LAYER {l} ;",
                f" RECT {r[0]:.3f} {r[1]:.3f} {r[2]:.3f} {r[3]:.3f} ;"," END"]
        L+=[f" END {p}"]
    # OBS: approximate blockage, kept clear of the pin ports above
    L+=[" OBS"," LAYER li1 ;",f" RECT 0 0 {TW:.3f} {H:.3f} ;",
        " LAYER met1 ;",
        f" RECT 0.600 0 {VG_RAIL_X0:.3f} {VG_RAIL[0]:.3f} ;",
        f" RECT 0 0 {STRAP_VSS-0.20:.3f} {lat:.3f} ;",
        f" RECT {STRAP_VDD+0.20:.3f} 0 {VG_RAIL_X0:.3f} {lat:.3f} ;",
        " LAYER met2 ;",
        f" RECT 0.600 0 {TW:.3f} 0.400 ;",
        f" RECT 6.600 0 {TW:.3f} {lat:.3f} ;",
        f" RECT 0.600 {lat+2.8:.3f} {TW:.3f} {VP_RAIL[0]:.3f} ;",
        " LAYER met3 ;",
        f" RECT 0.600 0 {xsp-0.25:.3f} {H:.3f} ;",
        f" RECT {xsp+0.25:.3f} 0 {W-1.0:.3f} {H:.3f} ;",
        " LAYER met4 ;",
        f" RECT 0 0 {xsp-0.25:.3f} {H:.3f} ;",
        f" RECT {xsp+0.25:.3f} 0 {W:.3f} {H:.3f} ;"," END",
        f"END {name}","END LIBRARY"]
    open(os.path.join(out_dir,"arbchain.lef"),"w").write("\n".join(L)+"\n")

    vh=["`ifdef USE_POWER_PINS","`celldefine",
        f"module {name} (",
        f" output q, input launch, input arb_rst_n, input [{STAGES-1}:0] ch,",
        " input VPWR, input VGND"," );","endmodule","`endcelldefine","`else",
        f"module {name} (",
        f" output q, input launch, input arb_rst_n, input [{STAGES-1}:0] ch",
        " );","endmodule","`endif"]
    open(os.path.join(out_dir,"arbchain.vh"),"w").write("\n".join(vh)+"\n")

    # pure structural netlist (no assigns)
    PWR_ON="".join(["`ifdef USE_POWER_PINS",
                    " , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)",
                    "`endif"])
    nl=["// gate-level netlist (pure structural - no continuous assigns)",
        "`ifdef USE_POWER_PINS","`celldefine",
        f"module {name} (",
        f" output q, input launch, input arb_rst_n, input [{STAGES-1}:0] ch,",
        " input VPWR, input VGND"," );","`else",
        f"module {name} (",
        f" output q, input launch, input arb_rst_n, input [{STAGES-1}:0] ch",
        " );","`endif",
        f" wire [{STAGES}:0] top;",f" wire [{STAGES}:0] bot;"]
    for g in range(STAGES):
        src="launch" if g==0 else None
        at,bt=(src,src) if src else (f"top[{g}]",f"bot[{g}]")
        ab,bb=(src,src) if src else (f"bot[{g}]",f"top[{g}]")
        nl+=[f" sky130_fd_sc_hd__mux2_1 u_t{g} (",
             f" .A0({at}), .A1({bt}), .S(ch[{g}]), .X(top[{g+1}])",
             PWR_ON," );",
             f" sky130_fd_sc_hd__mux2_1 u_b{g} (",
             f" .A0({ab}), .A1({bb}), .S(ch[{g}]), .X(bot[{g+1}])",
             PWR_ON," );"]
    nl+=[f" sky130_fd_sc_hd__dlrtp_1 u_latch (",
         f" .D(top[{STAGES}]), .GATE(bot[{STAGES}]), "
         f".RESET_B(arb_rst_n), .Q(q)",
         PWR_ON," );","endmodule","`endcelldefine"]
    open(os.path.join(out_dir,"arbchain.nl.v"),"w").write("".join(nl)+"\n")

    # liberty
    L2=[]; a=L2.append
    a("library (arbchain_lib) {")
    a(" delay_model : table_lookup;")
    a(' time_unit : "1ns";'); a(' voltage_unit : "1V";')
    a(' current_unit : "1mA";'); a(' pulling_resistance_unit : "1kohm";')
    a(" capacitive_load_unit (1.0, pf);")
    a(' leakage_power_unit : "1nW";')
    for t in ("input_threshold_pct_rise : 50;","input_threshold_pct_fall : 50;",
              "output_threshold_pct_rise : 50;","output_threshold_pct_fall : 50;",
              "slew_lower_threshold_pct_rise : 10;",
              "slew_lower_threshold_pct_fall : 10;",
              "slew_upper_threshold_pct_rise : 90;",
              "slew_upper_threshold_pct_fall : 90;"): a(" "+t)
    a(" nom_process : 1.0;"); a(" nom_voltage : 1.80;")
    a(" nom_temperature : 25;")
    a(" operating_conditions (nom_tt_025C_1v80) {")
    a(" process : 1.0;"); a(" voltage : 1.80;"); a(" temperature : 25;"); a(" }")
    a(" default_operating_conditions : nom_tt_025C_1v80;")
    a(f" type (bus{STAGES}) {{")
    a(f" bit_width : {STAGES};"); a(f" bit_from : {STAGES-1};")
    a(" bit_to : 0;"); a(" }")
    a(f" cell ({name}) {{")
    a(f" area : {TW*H:.2f};")
    a(" pg_pin (VPWR) { voltage_name : VPWR; pg_type : primary_power; }")
    a(" pg_pin (VGND) { voltage_name : VGND; pg_type : primary_ground; }")
    a(" pin (launch) { direction : input; capacitance : 0.03; "
      "max_capacitance : 0.5; }")
    a(" pin (arb_rst_n) { direction : input; capacitance : 0.02; "
      "max_capacitance : 0.5; }")
    a(" bus (ch) {"); a(f" bus_type : bus{STAGES};")
    a(" direction : input;"); a(" capacitance : 0.04;")
    a(" max_capacitance : 0.5;"); a(" }")
    a(" pin (q) { direction : output; capacitance : 0.05; "
      "max_capacitance : 0.5; }")
    a(" }"); a("}")
    with open(os.path.join(out_dir,"arbchain.lib"),"w") as fh:
        fh.write("".join(L2)+"\n")

if __name__=="__main__":
    main()
