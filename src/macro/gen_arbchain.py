#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# gen_arbchain.py  (DRC-clean revision 2)
#
# Revision-2 changes (map to remaining ~7k violations):
#  [R2-1]  All drawn coordinates snapped to 5nm manufacturing grid
#           -> clears *_OFFGRID (ct/m1/m2/m3/m4/via2/via3 OFFGRID).
#  [R2-2]  mcon drawn exactly 0.17, centred on the *li polygon* centre
#           (li ∩ LEF-rect), not the LEF bbox centre -> ct.1 / ct.4.
#  [R2-3]  via(68,44) drawn exactly 0.15 -> via.1a.
#  [R2-4]  m1 pin pad = 0.26 x 0.32  (m1.4 0.03, m1.5 0.06, m1.6 area,
#           m1.2 spacing 0.4-0.26=0.14) -> m1.2/m1.6/m1.7.
#  [R2-5]  m2 pad over via1 = 0.26 x 0.32 (m2.4 0.055, m2.5 0.085, m2.2)
#  [R2-6]  via2/via3 no longer sit on the pin pad.  A short m2 (m3)
#           stub runs to a per-pin *staggered channel row* and the
#           via is placed there with a proper pad:
#             via2 = 0.20, m2 pad 0.28 x 0.37 (via2.4 0.04 / via2.5 0.085)
#             m3 pad over via2 = 0.34 x 0.34 (m3.4 0.065, m3.6 area)
#             via3 = 0.20, m3 pad 0.38 x 0.38 (via3.5 0.09)
#             m4 pad over via3 = 0.34 x 0.34 (m4.3 0.065)
#  [R2-7]  m3 / m4 wires 0.30 wide; m3 channels 0.68 apart, m4 spines
#           >=0.7 apart -> m3.2/m3.3ab/m4.1/m4.2.
#  [R2-8]  prBoundary on (235,0).
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
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
STAGES=24; MUX_W,MUX_H=4.14,2.72; LATCH_W,LATCH_H=5.98,2.72
PITCH,GAP=3.40,1.5; CH=2*GAP; W=2*(GAP+MUX_W); XC=W/2; YOFF=0.24
H=(STAGES+1)*PITCH+2*YOFF
MUX_LEF="sky130_fd_sc_hd__mux2_1"; LATCH_LEF="sky130_fd_sc_hd__dlrtp_1"

GRID=0.005
LAY_LI1 =(67,20); LAY_MET1=(68,20); LAY_MET2=(69,20)
LAY_MET3=(70,20); LAY_MET4=(71,20)
LAY_MCON=(67,44); LAY_VIA1=(68,44); LAY_VIA2=(69,44); LAY_VIA3=(70,44)
LAY_PR  =(235,4)                      # [R2-8]

EV={"a0":0.8,"a1t":0.40,"a1b":0.74,"x":1.26,"ch":1.06}
OD=dict(EV)
STRAPS={"VSS_L":4.70,"VDD_L":5.10,"VDD_R":6.48,"VSS_R":6.88}
# [R2-7] m4 spines >=0.7 apart
PAIR_A=(4.60,6.00); PAIR_B=(5.30,6.70); LAUNCH_X=3.90
MACRO_X,MACRO_Y=83.30,7.20
CORR_W=6.00; TW=W+CORR_W
VP_RAIL=(H-0.70,H); VP_RAIL_X=14.95
VG_RAIL=(H-0.68,H-0.01); VG_RAIL_X0=STRAPS["VSS_R"]-0.09
ACCESS_MAX=1.34

# [R2-3..R2-6] exact via sizes + pad rectangles (dx,dy)
MCON=0.17; V1=0.15; V2=0.20; V3=0.20
M1P_V1 =(0.26,0.32)
M2P_V1 =(0.26,0.32)
M2P_V2 =(0.28,0.37)
M3P_V2 =(0.34,0.34)
M3P_V3 =(0.38,0.38)
M4P_V3 =(0.34,0.34)
W_M3,W_M4=0.30,0.30
# [R2-6] staggered m2/m3 channel rows (per row, 0.68 apart)
CH_M2=(0.46,1.14); CH_M3=(0.34,1.02,1.70)

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
    # [R2-2] centre of the largest li polygon inside the LEF rect
    def li_pin_center(self,pin,trans):
        dbu=self.dbu; best=None; best_a=0
        for layer,r in self.pins.get(pin,[]):
            if layer!="li1": continue
            rb=pya.Box(round(r[0]/dbu),round(r[1]/dbu),
                       round(r[2]/dbu),round(r[3]/dbu)).transformed(trans)
            for po in self.pin_metal.get(pin,pya.Region()).each():
                if po.bbox().inside(rb):
                    a=po.area()
                    if a>best_a: best_a=a; best=po.bbox()
        if best is None: return None
        return (best.center().x*dbu, best.center().y*dbu)

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
    def h(self,layer,y,x0,x1,w=None):
        w=w if w is not None else W_M3 if layer==LAY_MET3 else W_M4 if layer==LAY_MET4 else 0.17
        self.box(layer,x0,y-w/2,x1,y+w/2)
    def v(self,layer,x,y0,y1,w=None):
        w=w if w is not None else W_M3 if layer==LAY_MET3 else W_M4 if layer==LAY_MET4 else 0.17
        self.box(layer,x-w/2,y0,x+w/2,y1)

def row_tracks(g): return EV if g%2==0 else OD
MET3_XOFF,MET3_XPITCH=0.34,0.68

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

    def top_trans(g): return pya.Trans(0,False,0,round((g*PITCH+YOFF)*1000))
    def bot_trans(g): return (pya.Trans(0,False,round(W*1000),round((g*PITCH+YOFF)*1000))*pya.Trans.M90)
    def latch_trans(y): return pya.Trans(0,False,round(((W-LATCH_W)/2)*1000),round(y*1000))

    for g in range(STAGES):
        macro.insert(pya.CellInstArray(mux_ref,top_trans(g)))
        macro.insert(pya.CellInstArray(mux_ref,bot_trans(g)))
    ly_r=STAGES*PITCH+YOFF
    macro.insert(pya.CellInstArray(latch_ref,latch_trans(ly_r)))

    # ---------- [R2-2..R2-6] rule-correct primitives ----------
    def mcon_at(cell,trans,pin,y_track):
        c=cell.li_pin_center(pin,trans)
        if c is None: return None
        cx,cy=snap(c[0]),snap(c[1])
        d.box(LAY_MCON,cx-MCON/2,cy-MCON/2,cx+MCON/2,cy+MCON/2)
        return (cx,cy)
    def rect_c(layer,dx,dy,x,y):
        d.box(layer,x-dx/2,y-dy/2,x+dx/2,y+dy/2)
    def stack_m1(cell,trans,pin,y_track):
        c=mcon_at(cell,trans,pin,y_track)
        if c is None: return None
        rect_c(LAY_MET1,*M1P_V1,*c); rect_c(LAY_MET2,*M2P_V1,*c)
        d.box(LAY_VIA1,c[0]-V1/2,c[1]-V1/2,c[0]+V1/2,c[1]+V1/2)
        return c
    def to_m2_channel(cell,trans,pin,y_track,ch_y,stag):
        c=stack_m1(cell,trans,pin,y_track)
        if c is None: return None
        cy=ch_y+ (0.34 if stag else 0.0)
        d.v(LAY_MET2,c[0],min(c[1],cy),max(c[1],cy))
        vy=snap(cy)
        rect_c(LAY_MET2,*M2P_V2,c[0],vy)
        d.box(LAY_VIA2,c[0]-V2/2,vy-V2/2,c[0]+V2/2,vy+V2/2)
        rect_c(LAY_MET3,*M3P_V2,c[0],vy)
        return (c[0],vy)
    def to_m3_channel(x,vy,ch_y):
        cy=snap(ch_y)
        d.v(LAY_MET3,x,min(vy,cy),max(vy,cy))
        rect_c(LAY_MET3,*M3P_V3,x,cy)
        d.box(LAY_VIA3,x-V3/2,cy-V3/2,x+V3/2,cy+V3/2)
        rect_c(LAY_MET4,*M4P_V3,x,cy)
        return (x,cy)
    def to_m4(x,cy):
        rect_c(LAY_MET4,*M4P_V3,x,cy)
        return (x,cy)
    def h3(y,x0,x1): d.h(LAY_MET3,y,x0,x1,W_M3)
    def h4(y,x0,x1): d.h(LAY_MET4,y,x0,x1,W_M4)
    def v4(x,y0,y1): d.v(LAY_MET4,x,y0,y1,W_M4)

    # ---------- stage 0 S ----------
    tc0=row_tracks(0)
    s1=to_m2_channel(mux,top_trans(0),"S",YOFF+tc0["ch"],YOFF+CH_M2[0],0)
    s2=to_m2_channel(mux,bot_trans(0),"S",YOFF+tc0["ch"],YOFF+CH_M2[0],0)
    if s1 and s2:
        d.h(LAY_MET2,YOFF+CH_M2[0],0.0,max(s1[0],s2[0]),0.17)

    # ---------- stages ----------
    for g in range(1,STAGES):
        y_prev=(g-1)*PITCH+YOFF; y_cur=g*PITCH+YOFF
        tp=row_tracks(g-1); tc=row_tracks(g)
        X_T,X_B=(PAIR_A if g%2==0 else PAIR_B)
        st=g%2
        # top path
        src=to_m2_channel(mux,top_trans(g-1),"X",y_prev+tp["x"],y_prev+CH_M2[st],st)
        a0 =to_m2_channel(mux,top_trans(g),"A0",y_cur+tc["a0"],y_cur+CH_M2[1-st],1-st)
        a1 =to_m2_channel(mux,bot_trans(g),"A1",y_cur+tc["a1b"],y_cur+CH_M2[st],st)
        if src and a0 and a1:
            d.h(LAY_MET2,src[1],src[0],X_T,0.17)
            d.h(LAY_MET2,a0[1],a0[0],X_T,0.17)
            d.h(LAY_MET2,a1[1],a1[0],X_T,0.17)
            d.v(LAY_MET2,X_T,min(src[1],a0[1],a1[1]),max(src[1],a0[1],a1[1]),0.17)
            m3t=to_m3_channel(X_T,a1[1],y_cur+CH_M3[st])
            m3t2=to_m3_channel(X_T,src[1],y_prev+CH_M3[1-st])
            m3t3=to_m3_channel(X_T,a0[1],y_cur+CH_M3[1-st])
        # bot path
        src=to_m2_channel(mux,bot_trans(g-1),"X",y_prev+tp["x"],y_prev+CH_M2[1-st],1-st)
        a1 =to_m2_channel(mux,top_trans(g),"A1",y_cur+tc["a1t"],y_cur+CH_M2[st],st)
        a0 =to_m2_channel(mux,bot_trans(g),"A0",y_cur+tc["a0"],y_cur+CH_M2[1-st],1-st)
        if src and a1 and a0:
            d.h(LAY_MET2,src[1],X_B,src[0],0.17)
            d.h(LAY_MET2,a1[1],a1[0],X_B,0.17)
            d.h(LAY_MET2,a0[1],X_B,a0[0],0.17)
            d.v(LAY_MET2,X_B,min(src[1],a1[1],a0[1]),max(src[1],a1[1],a0[1]),0.17)
        # S
        s1=to_m2_channel(mux,top_trans(g),"S",y_cur+tc["ch"],y_cur+CH_M2[st],st)
        s2=to_m2_channel(mux,bot_trans(g),"S",y_cur+tc["ch"],y_cur+CH_M2[st],st)
        if s1 and s2:
            d.h(LAY_MET2,y_cur+CH_M2[st],0.0,max(s1[0],s2[0]),0.17)

    # ---------- stage-0 launch ----------
    xc=snap(LAUNCH_X)
    la0=to_m2_channel(mux,top_trans(0),"A0",YOFF+tc0["a0"],YOFF+CH_M2[0],0)
    lb0=to_m2_channel(mux,bot_trans(0),"A0",YOFF+tc0["a0"],YOFF+CH_M2[0],0)
    la1=to_m2_channel(mux,top_trans(0),"A1",YOFF+tc0["a1t"],YOFF+CH_M2[1],1)
    lb1=to_m2_channel(mux,bot_trans(0),"A1",YOFF+tc0["a1b"],YOFF+CH_M2[0],0)
    if la0 and lb0:
        d.h(LAY_MET2,la0[1],la0[0],xc,0.17); d.h(LAY_MET2,lb0[1],xc,lb0[0],0.17)
    if la1: m3l=to_m3_channel(xc,la1[1],YOFF+CH_M3[1]); to_m4(xc,m3l[1])
    if lb1: m3l=to_m3_channel(xc,lb1[1],YOFF+CH_M3[0]); to_m4(xc,m3l[1])
    d.v(LAY_MET4,xc,0.0,YOFF+CH_M3[1],W_M4)
    d.box(LAY_MET4,xc-W_M4/2,0,xc+W_M4/2,0.70)

    # ---------- latch ----------
    ylat=ly_r; tp=row_tracks(STAGES-1); X_T,X_B=PAIR_A
    src=to_m2_channel(mux,top_trans(STAGES-1),"X",ylat-PITCH+tp["x"],ylat-PITCH+CH_M2[0],0)
    dp =to_m2_channel(latch,latch_trans(ylat),"D",ylat+1.2,ylat+CH_M2[1],1)
    if src and dp:
        d.h(LAY_MET2,src[1],src[0],X_T,0.17)
        d.h(LAY_MET2,dp[1],dp[0],X_T,0.17)
        d.v(LAY_MET2,X_T,min(src[1],dp[1]),max(src[1],dp[1]),0.17)
    src=to_m2_channel(mux,bot_trans(STAGES-1),"X",ylat-PITCH+tp["x"],ylat-PITCH+CH_M2[1],1)
    gp =to_m2_channel(latch,latch_trans(ylat),"GATE",ylat+1.0,ylat+CH_M2[0],0)
    if src and gp:
        d.h(LAY_MET2,src[1],X_B,src[0],0.17)
        d.h(LAY_MET2,gp[1],gp[0],X_B,0.17)
        d.v(LAY_MET2,X_B,min(src[1],gp[1]),max(src[1],gp[1]),0.17)
    # q / rst on m3, staggered
    q_track=snap(ylat+2.04); rst_track=snap(ylat+2.72)
    qp=to_m2_channel(latch,latch_trans(ylat),"Q",q_track,q_track,0)
    if qp:
        m3q=to_m3_channel(qp[0],qp[1],q_track); h3(q_track,qp[0],TW); to_m4(TW-0.34,m3q[1])
    rp=to_m2_channel(latch,latch_trans(ylat),"RESET_B",rst_track,rst_track,0)
    if rp:
        m3r=to_m3_channel(rp[0],rp[1],rst_track); h3(rst_track,0,rp[0])

    # ---------- power ----------
    # [FIX 6] VSS_L / VDD_L 两条 met1 strap 不再穿过 latch 行：
    # strap 与 latch 内部 met1 围出两个面积 < 0.14um2 的 m1 孔 (m1.7)。
    # latch 的 VPWR/VGND met1 rail 由 VDD_R/VSS_R strap 直接搭接供电，
    # 左 strap 只需服务 mux 行，截止到最后一级 mux 顶部即可。
    MUX_TOP = STAGES * PITCH + YOFF          # = 81.84，最后一级 mux 顶部
    for name, x in STRAPS.items():
        y_top = H if name in ("VDD_R", "VSS_R") else MUX_TOP
        d.v(LAY_MET1, x, 0, y_top)
    def rail_bands(cell,tr,pin):
        out=set()
        for layer,r in cell.pins.get(pin,[]):
            if layer=="met1" and (r[2]-r[0])>=MUX_W-0.01:
                out.add((round(r[1],3),round(r[3],3)))
        return out
    for g in range(STAGES):
        y=g*PITCH+YOFF; t=top_trans(g); b=bot_trans(g)
        bands={}
        for tr in (t,b):
            for net,pin in (("VDD","VPWR"),("VSS","VGND")):
                bands.setdefault(net,set()).update(rail_bands(mux,tr,pin))
        for net,ys in bands.items():
            for y0,y1 in ys:
                ym=(y0+y1)/2
                if ym<=y+MUX_H+0.01: d.h(LAY_MET2,ym,0,TW,0.17)
        for tr,sx in ((t,STRAPS["VDD_L"]),(t,STRAPS["VSS_L"]),
                      (b,STRAPS["VDD_R"]),(b,STRAPS["VSS_R"])):
            pin="VPWR" if sx in (STRAPS["VDD_L"],STRAPS["VDD_R"]) else "VGND"
            for y0,y1 in rail_bands(mux,tr,pin):
                ym=snap((y0+y1)/2)
                d.box(LAY_VIA1,sx-V1/2,ym-V1/2,sx+V1/2,ym+V1/2)
                rect_c(LAY_MET1,*M1P_V1,sx,ym); rect_c(LAY_MET2,*M2P_V1,sx,ym)
    for pin,net in (("VPWR","VDD"),("VGND","VSS")):
        s1=STRAPS["VDD_L"] if net=="VDD" else STRAPS["VSS_L"]
        for y0,y1 in rail_bands(latch,latch_trans(ylat),pin):
            ym=(y0+y1)/2
            d.h(LAY_MET2,ym,s1,TW,0.17)
            d.box(LAY_VIA1,s1-V1/2,ym-V1/2,s1+V1/2,ym+V1/2)
            rect_c(LAY_MET1,*M1P_V1,s1,ym); rect_c(LAY_MET2,*M2P_V1,s1,ym)
    d.box(LAY_MET2,0,VP_RAIL[0],VP_RAIL_X,VP_RAIL[1])
    d.box(LAY_MET1,VG_RAIL_X0,VG_RAIL[0],TW,VG_RAIL[1])
    for sx in (STRAPS["VDD_L"],STRAPS["VDD_R"]):
        if sx<VP_RAIL_X:
            ym=snap((VP_RAIL[0]+VP_RAIL[1])/2)
            d.box(LAY_VIA1,sx-V1/2,ym-V1/2,sx+V1/2,ym+V1/2)
            rect_c(LAY_MET1,*M1P_V1,sx,ym); rect_c(LAY_MET2,*M2P_V1,sx,ym)
    d.box((235, 4), 0, 0, TW, H)
    d.box((236, 0), 0, 0, TW, H)

    out_dir=args.out; os.makedirs(out_dir,exist_ok=True)
    gds=os.path.join(out_dir,"arbchain.gds"); ly.write(gds); print("wrote",gds)
    with open(os.path.join(out_dir,"arbchain_routing.json"),"w") as fh:
        json.dump([{"layer":list(l),"box":[round(v,3) for v in b]} for l,b in d.shapes],fh)
    pin_coords={"q_y":q_track,"rst_y":rst_track,"launch_x":xc,"launch_y":0.70}
    emit_artifacts(out_dir,pin_coords)

def emit_artifacts(out_dir,pc):
    name="arbchain"; lat=STAGES*PITCH+YOFF
    def ch_y(g): return g*PITCH+YOFF+EV["ch"]
    def pr(l,x1,y1,x2,y2): return (l,(x1,y1,x2,y2))
    pins=[]
    for g in range(STAGES):
        pins.append((f"ch[{g}]","INPUT","SIGNAL",[pr("met3",0.0,ch_y(g)-0.15,0.30,ch_y(g)+0.15)]))
    xsp=pc["launch_x"]
    pins.append(("launch","INPUT","SIGNAL",[pr("met4",xsp-0.15,0.0,xsp+0.15,0.70)]))
    pins.append(("arb_rst_n","INPUT","SIGNAL",[pr("met3",0.0,pc["rst_y"]-0.15,0.30,pc["rst_y"]+0.15)]))
    pins.append(("q","OUTPUT","SIGNAL",[pr("met3",TW-0.68,pc["q_y"]-0.15,TW,pc["q_y"]+0.15)]))
    pins.append(("VPWR","INOUT","POWER",[pr("met2",W,VP_RAIL[0],TW,VP_RAIL[1])]))
    pins.append(("VGND","INOUT","GROUND",[pr("met1",W,VG_RAIL[0],TW,VG_RAIL[1])]))
    L=["# LEF abstract","VERSION 5.8 ;","BUSBITCHARS \"[]\" ;","DIVIDERCHAR \"/\" ;",
       f"MACRO {name}","  CLASS BLOCK ;","  ORIGIN 0 0 ;",
       f"  SIZE {TW:.3f} BY {H:.3f} ;","  SYMMETRY X Y ;"]
    for p,dirn,use,rects in pins:
        L+= [f"  PIN {p}",f"    DIRECTION {dirn} ;",f"    USE {use} ;"]
        for l,r in rects:
            L+=["    PORT",f"      LAYER {l} ;",f"        RECT {r[0]:.3f} {r[1]:.3f} {r[2]:.3f} {r[3]:.3f} ;","    END"]
        L+= [f"  END {p}"]
    L+=["  OBS","    LAYER li1 ;",f"      RECT 0 0 {TW:.3f} {H:.3f} ;",
        "    LAYER met1 ;",f"      RECT 0 0 16.600 {VP_RAIL[0]:.3f} ;",
        f"      RECT 16.600 0 {TW:.3f} {lat+0.24:.3f} ;",
        f"      RECT 16.600 {lat+2.0:.3f} {TW:.3f} {VP_RAIL[0]:.3f} ;",
        "    LAYER met2 ;",f"      RECT 0.600 0 16.600 {VP_RAIL[0]:.3f} ;",
        f"      RECT 16.600 0 {TW:.3f} {lat+0.085:.3f} ;",
        f"      RECT 16.600 {lat+2.0:.3f} {TW:.3f} {VP_RAIL[0]:.3f} ;",
        "    LAYER met3 ;",f"      RECT 0.600 0 {xsp-0.20:.3f} {H:.3f} ;",
        f"      RECT {xsp+0.20:.3f} 0 {W-1.0:.3f} {H:.3f} ;",
        "    LAYER met4 ;",f"      RECT 0 0 {xsp-0.25:.3f} {H:.3f} ;",
        f"      RECT {xsp+0.25:.3f} 0 {W:.3f} {H:.3f} ;","  END",
        f"END {name}","END LIBRARY"]
    open(os.path.join(out_dir,"arbchain.lef"),"w").write("\n".join(L)+"\n")
    # verilog views (unchanged, power-pin capable)
    vh=[ "`ifdef USE_POWER_PINS","`celldefine",f"module {name} (",
         f"  output q, input launch, input arb_rst_n, input [{STAGES-1}:0] ch,",
         "  input VPWR, input VGND","  );","endmodule","`endcelldefine","`else",
         f"module {name} (",f"  output q, input launch, input arb_rst_n, input [{STAGES-1}:0] ch","  );",
         "endmodule","`endif"]
    open(os.path.join(out_dir,"arbchain.vh"),"w").write("\n".join(vh)+"\n")
    # ============================================================
    # 重写：纯结构化 netlist（netgen 友好，无任何 `assign`）
    # ============================================================
    PWR_ON  = "".join(["`ifdef USE_POWER_PINS",
                    " , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)",
                    "`endif"])

    nl = ["// gate-level netlist (pure structural - no continuous assigns)",
        "`ifdef USE_POWER_PINS", "`celldefine",
        f"module {name} (",
        f" output q, input launch, input arb_rst_n, input [{STAGES-1}:0] ch,",
        " input VPWR, input VGND",
        " );",
        "`else",
        f"module {name} (",
        f" output q, input launch, input arb_rst_n, input [{STAGES-1}:0] ch",
        " );",
        "`endif",
        f" wire [{STAGES}:0] top;",
        f" wire [{STAGES}:0] bot;"]

    for g in range(STAGES):
        # stage 0 直接用 launch 播种，取代原来的 assign top[0]=launch
        src = "launch" if g == 0 else None
        at, bt = (src, src) if src else (f"top[{g}]", f"bot[{g}]")
        ab, bb = (src, src) if src else (f"bot[{g}]", f"top[{g}]")
        nl += [f" sky130_fd_sc_hd__mux2_1 u_t{g} (",
            f" .A0({at}), .A1({bt}), .S(ch[{g}]), .X(top[{g+1}])",
            PWR_ON, " );",
            f" sky130_fd_sc_hd__mux2_1 u_b{g} (",
            f" .A0({ab}), .A1({bb}), .S(ch[{g}]), .X(bot[{g+1}])",
            PWR_ON, " );"]

    nl += [f" sky130_fd_sc_hd__dlrtp_1 u_latch (",   # 直接连 wire，去掉 assign d/gate
        f" .D(top[{STAGES}]), .GATE(bot[{STAGES}]), .RESET_B(arb_rst_n), .Q(q)",
        PWR_ON, " );",
        "endmodule", "`endcelldefine"]
    open(os.path.join(out_dir, "arbchain.nl.v"), "w").write("".join(nl) + "\n")

    # ============================================================
    # 重写：合法 liberty（cell 块 + 阈值 + units）
    # ============================================================
    L2 = []
    a = L2.append
    a("library (arbchain_lib) {")
    a(" delay_model : table_lookup;")
    a(' time_unit : "1ns";')
    a(' voltage_unit : "1V";')
    a(' current_unit : "1mA";')
    a(' pulling_resistance_unit : "1kohm";')
    a(" capacitive_load_unit (1.0, pf);")
    a(' leakage_power_unit : "1nW";')
    # -- OpenROAD 强制要求的 8 个阈值（sky130 惯例 50 / 10 / 90）--
    a(" input_threshold_pct_rise : 50;")
    a(" input_threshold_pct_fall : 50;")
    a(" output_threshold_pct_rise : 50;")
    a(" output_threshold_pct_fall : 50;")
    a(" slew_lower_threshold_pct_rise : 10;")
    a(" slew_lower_threshold_pct_fall : 10;")
    a(" slew_upper_threshold_pct_rise : 90;")
    a(" slew_upper_threshold_pct_fall : 90;")
    a(" nom_process : 1.0;")
    a(" nom_voltage : 1.80;")
    a(" nom_temperature : 25;")
    a(" operating_conditions (nom_tt_025C_1v80) {")
    a("  process : 1.0;")
    a("  voltage : 1.80;")
    a("  temperature : 25;")
    a(" }")
    a(" default_operating_conditions : nom_tt_025C_1v80;")
    # -- 关键：cell 名必须与 LEF macro 名一致（arbchain），否则 ORD-2011 --
    a(f" cell ({name}) {{")
    a(f"  area : {TW*H:.2f};")
    a("  pg_pin (VPWR) { voltage_name : VPWR; pg_type : primary_power; }")
    a("  pg_pin (VGND) { voltage_name : VGND; pg_type : primary_ground; }")
    a("  pin (launch) { direction : input; capacitance : 0.03; max_capacitance : 0.5; }")
    a("  pin (arb_rst_n) { direction : input; capacitance : 0.02; max_capacitance : 0.5; }")
    for g in range(STAGES):
        a(f"  pin (ch[{g}]) {{ direction : input; capacitance : 0.04; max_capacitance : 0.5; }}")
    a("  pin (q) { direction : output; capacitance : 0.05; max_capacitance : 0.5; }")
    a(" }")
    a("}")
    with open(os.path.join(out_dir, "arbchain.lib"), "w") as fh:
        fh.write("".join(L2) + "\n")

if __name__=="__main__":
    main()