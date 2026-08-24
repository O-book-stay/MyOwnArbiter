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

import argparse, os, re, sys, json, urllib.request
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
CH_CH =1.595    # net ch[g]    : S(top g) + S(bot g)          (met2, in-row)
                #   1.80 collided with the X pin pad (bottom 2.06):
                #   X pad [2.06,2.38] vs ch band y+0.085 -> need y+0.085<=1.92
CH_BOT=3.20     # net bot[g+1] : A1(top g+1)+A0(bot g+1)+X(bot g)   (met2, gap)
CH_TOP=3.70     # net top[g+1] : A0(top g+1)+A1(bot g+1)+X(top g)   (met2, gap)

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

class Draw:
    def __init__(self,ly,top):
        self.ly=ly; self.top=top; self.layers={}; self.shapes=[]
    def l(self,layer):
        if layer not in self.layers:
            self.layers[layer]=self.ly.layer(layer[0],layer[1])
        return self.layers[layer]
    def box(self,layer,x1,y1,x2,y2):
        p1=pt(x1,y1); p2=pt(x2,y2)
        self.top.shapes(self.l(layer)).insert(pya.Box(p1[0],p1[1],p2[0],p2[1]))
        self.shapes.append((layer,(x1,y1,x2,y2)))
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
    channels=[]            # (y, x0, x1) of every drawn channel (join() crossing check)
    # pre-register the per-row power lines as obstacles so stubs that would
    # cross them become met3 risers ([R3-3] intent)
    for g in range(STAGES):
        y=g*PITCH+YOFF
        channels.append((y+0.24, RAIL_X0, BOT_VGN_X))   # per-row VSS line
        channels.append((y+2.96, RAIL_X0, BOT_VPW_X))   # per-row VDD line

    # ---------- [R3-2/R3-3] primitives ----------
    def rect_c(layer,dx,dy,x,y):
        d.box(layer,x-dx/2,y-dy/2,x+dx/2,y+dy/2)

    def mcon_at(cell,trans,pin):
        c=cell.li_pin_center(pin,trans)
        if c is None: return None
        cx,cy=snap(c[0]),snap(c[1])
        d.box(LAY_MCON,cx-MCON/2,cy-MCON/2,cx+MCON/2,cy+MCON/2)
        return (cx,cy)

    def pin_stack(cell,trans,pin):
        """li -> mcon -> met1 pad -> via1 -> met2 pad, at the li centre."""
        c=mcon_at(cell,trans,pin)
        if c is None: return None
        rect_c(LAY_MET1,*M1P_V1,*c); rect_c(LAY_MET2,*M2P_V1,*c)
        d.box(LAY_VIA1,c[0]-V1/2,c[1]-V1/2,c[0]+V1/2,c[1]+V1/2)
        return c

    def riser(c,ch_y,via2_at_top=True,tag=""):
        """met3 vertical from pin pad (via2 at pin) up/down to ch_y.
        Auto-jogs in x if it would violate met3 spacing. [R3-3]"""
        ya,yc=min(c[1],ch_y),max(c[1],ch_y)
        rect_c(LAY_MET2,*M2P_V2,*c)                       # grows the pin pad
        d.box(LAY_VIA2,c[0]-V2/2,c[1]-V2/2,c[0]+V2/2,c[1]+V2/2)
        rect_c(LAY_MET3,*M3P_V2,*c)
        n0=len(d.shapes)
        m=SPACING[LAY_MET3]
        def jclear(x1,y1,x2,y2):
            """strict spacing vs every pre-existing shape on met3 (own pad
            excluded: idx>=n0); overlaps are conflicts, not merges."""
            for idx,(lay,b) in enumerate(d.shapes):
                if lay!=LAY_MET3 or idx>=n0: continue
                dx=max(b[0]-(x2+m), x1-m-b[2], 0.0)
                dy=max(b[1]-(y2+m), y1-m-b[3], 0.0)
                if dx==0.0 and dy==0.0:
                    gx=max(b[0]-x2, x1-b[2], 0.0)
                    gy=max(b[1]-y2, y1-b[3], 0.0)
                    if gx==0.0 and gy==0.0: return False   # overlap/abut
                    if gx<m and gy<m: return False
            return True
        for dx in (0.0,0.65,-0.65,1.30,-1.30):
            xx=snap(c[0]+dx)
            if (jclear(xx-W_M3/2,ya,xx+W_M3/2,yc)
                    if dx==0.0 else
                jclear(min(c[0],xx)-W_M3/2,c[1]-W_M3/2,
                       max(c[0],xx)+W_M3/2,c[1]+W_M3/2)
                and jclear(xx-W_M3/2,ya,xx+W_M3/2,yc)):
                if dx!=0.0:
                    d.h(LAY_MET3,c[1],c[0],xx,W_M3)       # jog at the pin end
                d.v(LAY_MET3,xx,ya,yc,W_M3)
                if via2_at_top:
                    rect_c(LAY_MET2,*M2P_V2,xx,snap(ch_y))
                    d.box(LAY_VIA2,xx-V2/2,snap(ch_y)-V2/2,
                          xx+V2/2,snap(ch_y)+V2/2)
                    rect_c(LAY_MET3,*M3P_V2,xx,snap(ch_y))
                return xx
        warn(f"riser {tag}@{c}: no clear x, drawn straight")
        d.v(LAY_MET3,c[0],ya,yc,W_M3)
        if via2_at_top:
            rect_c(LAY_MET2,*M2P_V2,c[0],snap(ch_y))
            d.box(LAY_VIA2,c[0]-V2/2,snap(ch_y)-V2/2,
                  c[0]+V2/2,snap(ch_y)+V2/2)
            rect_c(LAY_MET3,*M3P_V2,c[0],snap(ch_y))
        return c[0]

    def join(c,ch_y,tag=""):
        """pin pad -> met2 stub if it crosses no foreign channel,
        otherwise met3 riser (decided at runtime). [R3-6]"""
        ya,yb=min(c[1],ch_y),max(c[1],ch_y)
        rx0,ry0,rx1,ry1 = c[0]-0.085, ya-0.085, c[0]+0.085, yb+0.085
        m=SPACING[LAY_MET2]
        for (cy,cx0,cx1) in channels:
            if abs(cy-ch_y)<=0.085: continue          # own channel: merge
            if rx0<=cx1+m and rx1>=cx0-m and ry0<=cy+0.085+m and ry1>=cy-0.085-m:
                return riser(c,ch_y,tag=tag)          # crosses a foreign channel
        if d.clear(LAY_MET2,rx0,ry0,rx1,ry1,m):
            d.v(LAY_MET2,c[0],ya,yb,0.17); return c[0]
        return riser(c,ch_y,tag=tag)

    def channel(y,xs):
        """met2 horizontal channel line over the x-extent of its members."""
        if not xs: return
        x0,x1=min(xs),max(xs)
        if not d.clear(LAY_MET2,x0,y-0.085,x1,y+0.085,SPACING[LAY_MET2]):
            warn(f"channel y={y}: tight against existing met2")
        d.h(LAY_MET2,y,x0,x1,0.17)
        channels.append((y,x0,x1))

    # ---------- ch[g] : both S pins -> in-row met2 line at +CH_CH ----------
    def ch_route(g):
        y0=g*PITCH+YOFF; cy=snap(y0+CH_CH); xs=[]
        for tr in (top_trans(g),bot_trans(g)):
            c=pin_stack(mux,tr,"S")
            if c is None: continue
            join(c,cy,tag=f"S{g}")
            xs.append(c[0])
        if xs: xs.append(0.0)          # reach the left-edge LEF pin
        channel(cy,xs)
        return cy

    ch_y_of={}
    for g in range(STAGES):
        ch_y_of[g]=ch_route(g)

    # ---------- [R3-5] stage-0 launch seeding ----------
    xc=snap(LAUNCH_X)
    lxs=[]
    for tr in (top_trans(0),bot_trans(0)):
        for pin in ("A0","A1"):
            c=pin_stack(mux,tr,pin)
            if c is None: continue
            riser(c,LAUNCH_Y,via2_at_top=False,tag=f"L{pin}")  # merge on met3
            lxs.append(c[0])
    if lxs:
        d.h(LAY_MET3,LAUNCH_Y,min(min(lxs),xc),max(max(lxs),xc),W_M3)
        d.v(LAY_MET3,xc,0.45,LAUNCH_Y,W_M3)
        rect_c(LAY_MET3,*M3P_V3,xc,0.45)
        d.box(LAY_VIA3,xc-V3/2,0.45-V3/2,xc+V3/2,0.45+V3/2)
        rect_c(LAY_MET4,*M4P_V3,xc,0.45)
        d.v(LAY_MET4,xc,0.0,0.45,W_M4)
        d.box(LAY_MET4,xc-W_M4/2,0,xc+W_M4/2,0.70)

    # ---------- stages 1..15 : gap channels between row g-1 and row g ----------
    for g in range(1,STAGES):
        y0=(g-1)*PITCH+YOFF
        cb=snap(y0+CH_BOT); ct=snap(y0+CH_TOP)
        tp,bb=top_trans(g),bot_trans(g); tpv,bbv=top_trans(g-1),bot_trans(g-1)
        # members (pads first, so stub conflict checks see everything)
        a1t=pin_stack(mux,tp,"A1"); a0b=pin_stack(mux,bb,"A0")   # net bot[g]
        a0t=pin_stack(mux,tp,"A0"); a1b=pin_stack(mux,bb,"A1")   # net top[g]
        xt =pin_stack(mux,tpv,"X"); xb =pin_stack(mux,bbv,"X")
        channel(cb,[c[0] for c in (a1t,a0b,xb) if c])
        channel(ct,[c[0] for c in (a0t,a1b,xt) if c])
        for c,y,t in ((a1t,cb,"a1t"),(a0b,cb,"a0b"),(xb,cb,f"Xb{g-1}"),
                      (a0t,ct,"a0t"),(a1b,ct,"a1b"),(xt,ct,f"Xt{g-1}")):
            if c: join(c,y,tag=f"{t}@r{g}")

    # ---------- latch : nets top[16] / bot[16] live in gap 15 ----------
    ylat=ly_r; y15=(STAGES-1)*PITCH+YOFF
    cb=snap(y15+CH_BOT); ct=snap(y15+CH_TOP)
    xt=pin_stack(mux,top_trans(STAGES-1),"X")
    xb=pin_stack(mux,bot_trans(STAGES-1),"X")
    dp=pin_stack(latch,latch_trans(ylat),"D")       # D  <- top[16]
    gp=pin_stack(latch,latch_trans(ylat),"GATE")    # GATE <- bot[16]
    channel(cb,[c[0] for c in (gp,xb) if c])
    channel(ct,[c[0] for c in (dp,xt) if c])
    if gp: join(gp,cb,tag="GATE")
    if xb: join(xb,cb,tag="Xb15")
    if dp: join(dp,ct,tag="D")
    if xt: join(xt,ct,tag="Xt15")

    # q / arb_rst_n on met3 tracks above the latch [R3-7]
    q_track=snap(ylat+2.40); rst_track=snap(ylat+3.05)
    qp=pin_stack(latch,latch_trans(ylat),"Q")
    if qp:
        riser(qp,q_track,tag="Q")
        d.h(LAY_MET3,q_track,min(qp[0],TW-0.34),TW,W_M3)
        rect_c(LAY_MET3,*M3P_V3,TW-0.34,q_track)
        d.box(LAY_VIA3,TW-0.34-V3/2,q_track-V3/2,TW-0.34+V3/2,q_track+V3/2)
        rect_c(LAY_MET4,*M4P_V3,TW-0.34,q_track)
    rp=pin_stack(latch,latch_trans(ylat),"RESET_B")
    if rp:
        riser(rp,rst_track,tag="RST")
        d.h(LAY_MET3,rst_track,0.0,rp[0],W_M3)

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
    d.v(LAY_MET2,15.40,snap(MUX_TOP+0.06),vgm,0.17)
    d.h(LAY_MET2,vgm,15.40,TW-0.28,0.17)
    v1_at(16.40,vgm)

    d.box(LAY_PR,0,0,TW,H)
    d.box((236,0),0,0,TW,H)

    # ---------- [R3-6] whole-figure spacing preview ----------
    def preview():
        sh=[(l,b) for (l,b) in d.shapes if l in SPACING]
        n=len(sh)
        for i in range(n):
            l1,b1=sh[i]
            for j in range(i+1,n):
                l2,b2=sh[j]
                if l1!=l2: continue
                m=SPACING[l1]
                gx=max(b1[0]-b2[2], b2[0]-b1[2], 0.0)
                gy=max(b1[1]-b2[3], b2[1]-b1[3], 0.0)
                if 0.0<gx<m and 0.0<gy<m:
                    warn(f"spacing {l1}: {b1} vs {b2} (gap {min(gx,gy):.3f})")
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
                 [pr("met4",xsp-0.15,0.0,xsp+0.15,0.70)]))
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
