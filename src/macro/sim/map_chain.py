#!/usr/bin/env python3
# ============================================================
# Reconstruct the arbchain mux-chain topology from the flat R+C
# PEX netlist (runs/macro_pex/arbchain_pex.spice) and emit
# runs/macro_pex/chain_map.json for the per-stage skew testbench.
#
# The flat netlist splits every wire into R-segmented fragments
# (`mux2_1_4/X`, `mux2_1_4/X.n0`, `.../X.t1`, ...). Electrical nets
# are the R-graph: ONLY R line endpoints are unioned (transistors
# are devices hanging off nets, NOT wires). Then:
#
#   stage of mux N   : its S-gate transistors (gate net = N/S.t*
#                      fragment) resolve, through R, to ch[g]
#   A0/A1 drivers    : a transistor is an INPUT transistor iff its
#                      gate component contains an external driver
#                      ('launch', a bare mux2_1_M/X pin, or ch[g]);
#                      the mux2_1 cell's internal terminal names
#                      (a_218_374# / a_439_47# -> A0,
#                       a_535_374# / a_218_47#  -> A1) then tell the
#                      pin, and the component tells the driver
#   D / GATE anchors : dlrtp_1_0 transistors with gate fragments
#                      dlrtp_1_0/D.* (resp. GATE.*) resolve to the
#                      mux feeding D (resp. GATE)
#
# Chain convention (src/arbiter_chain.v):
#   top[g+1] = c_g ? bot[g] : top[g]   (top mux: A0=top[g], A1=bot[g])
#   bot[g+1] = c_g ? top[g] : bot[g]   (bot mux: A0=bot[g], A1=top[g])
#   top[0] = bot[0] = launch;  D <- top[16], GATE <- bot[16]
# so the D-anchored mux is the stage-15 TOP mux and the walk runs
# backward: A0-driver of (g,T) = (g-1,T), A1-driver of (g,T) = (g-1,B).
#
# Usage:  python3 map_chain.py --pex <netlist> -o <chain_map.json>
# ============================================================

import argparse
import json
import re
import sys

CELL = "sky130_fd_sc_hd__mux2_1_"
DFF = "sky130_fd_sc_hd__dlrtp_1_0/"

RE_XPIN = re.compile(r"^sky130_fd_sc_hd__mux2_1_(\d+)/X$")
RE_CH = re.compile(r"^ch\[(\d+)\]$")

# mux2_1 cell-internal terminal names that identify the input pin
# (from the extracted cell view, magic flat naming)
A0_LOCAL = ("a_218_374#", "a_439_47#")
A1_LOCAL = ("a_535_374#", "a_218_47#")


def read_elements(path):
    """Return (xfers, rlines).

    magic ext2spice MOS lines are: X<name> d g s b model ad=.. pd=..
    so only the first 4 tokens after the name are nets.
    """
    xfers, rlines = [], []
    for raw in open(path):
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        tok = line.split()
        if tok[0][0] in "Xx":
            xfers.append(tok[1:5])          # [drain, gate, source, bulk]
        elif tok[0][0] in "Rr":
            rlines.append((tok[1], tok[2]))
    return xfers, rlines


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb

    def members(self):
        out = {}
        for n in self.p:
            out.setdefault(self.find(n), []).append(n)
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pex", required=True, help="flat R+C PEX netlist")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    xfers, rlines = read_elements(args.pex)
    dsu = DSU()

    # ---- nets = the R graph only (transistors are NOT wires) ----
    for nets in xfers:
        for n in nets:
            dsu.find(n)
    for a, b in rlines:
        dsu.union(a, b)
    comp_members = dsu.members()

    def mux_insts_in(members):
        out = set()
        for n in members:
            m = re.match(r"^sky130_fd_sc_hd__mux2_1_(\d+)/", n)
            if m:
                out.add(int(m.group(1)))
        return out

    def comp_stage(comp):
        for n in comp_members.get(comp, []):
            m = RE_CH.match(n)
            if m:
                return int(m.group(1))
        return None

    def comp_single_mux(members, what):
        insts = mux_insts_in(members)
        if len(insts) != 1:
            raise SystemExit(f"ERROR: dlrtp {what} input component touches "
                             f"{sorted(insts)} mux instances")
        return insts.pop()

    # ---- pass A: stage of every mux, from its S-gate components ----
    inst = {}                      # N -> {stage, a0, a1, a0_gate, a1_gate}
    for nets in xfers:
        m = re.match(r"^sky130_fd_sc_hd__mux2_1_(\d+)/S\.", nets[1])
        if not m:
            continue
        ni = int(m.group(1))
        if ni not in inst:
            inst[ni] = {"stage": None, "a0": None, "a1": None,
                        "a0_gate": None, "a1_gate": None}
        if inst[ni]["stage"] is None:
            st = comp_stage(dsu.find(nets[1]))
            if st is None:
                raise SystemExit(f"ERROR: S gate of mux {ni} does not reach "
                                 f"any ch[g] net")
            inst[ni]["stage"] = st
    stage_of = {ni: d["stage"] for ni, d in inst.items()}

    # ---- pass B: input transistors + dlrtp anchors ----
    # The two muxes of one stage share their drivers cross-wise
    # (N.A0 = P.A1 = driver output), so an input-net component
    # legitimately contains {consumer, stage-mate, driver}. The driver
    # is therefore the member instance whose stage differs from the
    # consumer's - or 'launch' at stage 0.
    dff_in = {"D": None, "GATE": None}
    for nets in xfers:
        gate = nets[1]
        gcomp = dsu.find(gate)
        members = comp_members.get(gcomp, [])

        ni = None
        for n in (nets[0], nets[2]):
            m = re.match(r"^sky130_fd_sc_hd__mux2_1_(\d+)/", n)
            if m:
                ni = int(m.group(1))
                break

        if ni is None:
            if gate.startswith(DFF + "D."):
                dff_in["D"] = comp_single_mux(members, "D")
            elif gate.startswith(DFF + "GATE."):
                dff_in["GATE"] = comp_single_mux(members, "GATE")
            continue

        d = inst[ni]
        driver = None
        if "launch" in members:
            driver = "launch"
        else:
            cands = {m2 for m2 in mux_insts_in(members)
                     if stage_of.get(m2) != d["stage"]}
            if len(cands) > 1:
                raise SystemExit(f"ERROR: ambiguous driver for mux {ni} "
                                 f"({gate}): {sorted(cands)}")
            driver = cands.pop() if cands else None
        if driver is None:
            continue               # S-gated / internal transistor

        local = {n.split("/", 1)[1] for n in nets[:3]
                 if n.startswith(f"sky130_fd_sc_hd__mux2_1_{ni}/")}
        if any(l in A0_LOCAL for l in local):
            d["a0"], d["a0_gate"] = driver, gate
        elif any(l in A1_LOCAL for l in local):
            d["a1"], d["a1_gate"] = driver, gate

    # ---- output probe fragment per instance: prefer the X.t0 terminal
    #      (exists for every instance); fall back to the bare X pin ----
    probe = {}
    for nets in xfers:
        for n in nets[:3]:
            m = re.match(r"^sky130_fd_sc_hd__mux2_1_(\d+)/X\.t0$", n)
            if m:
                probe[int(m.group(1))] = n
    for ni in inst:
        if ni not in probe:
            bare = f"sky130_fd_sc_hd__mux2_1_{ni}/X"
            if bare in dsu.p:
                probe[ni] = bare
            else:
                raise SystemExit(f"ERROR: no output probe fragment for "
                                 f"mux instance {ni}")

    # ---- dlrtp anchors ----
    anchor = {}
    for k, drv in dff_in.items():
        if drv is None:
            raise SystemExit(f"ERROR: dlrtp {k} input transistor not found")
        if drv == "launch":
            raise SystemExit(f"ERROR: dlrtp {k} driven by launch?")
        anchor[k] = drv

    # ---- chain walk backward from the dlrtp ----
    T = {15: anchor["D"]}   # stage -> mux instance (top path)
    B = {15: anchor["GATE"]}
    for g in range(15, 0, -1):
        a0T, a1T = inst[T[g]]["a0"], inst[T[g]]["a1"]
        a0B, a1B = inst[B[g]]["a0"], inst[B[g]]["a1"]
        # every driver in the walk must be a mux instance; 'launch' or an
        # unresolvable (None) gate means a broken chain
        for v in (a0T, a1T, a0B, a1B):
            if not isinstance(v, int):
                raise SystemExit(f"ERROR: chain break at stage {g}: driver "
                                 f"{v!r} is not a mux instance")
        # A0 of top mux = previous top; A1 of top mux = previous bot
        # A0 of bot mux = previous bot; A1 of bot mux = previous top
        if a0T != a1B or a0B != a1T:
            raise SystemExit(
                f"ERROR: chain break at stage {g}: T[{g}] a0={a0T} a1={a1T}; "
                f"B[{g}] a0={a0B} a1={a1B}")
        T[g - 1], B[g - 1] = a0T, a0B

    # root check: all stage-0 inputs are launch
    for k in ("a0", "a1"):
        for side, name in ((T, "top"), (B, "bot")):
            if inst[side[0]][k] != "launch":
                raise SystemExit(f"ERROR: stage-0 {name} mux {k}="
                                 f"{inst[side[0]][k]} != launch")
    # stage check
    for g in range(16):
        for side, name in ((T, "top"), (B, "bot")):
            if inst[side[g]]["stage"] != g:
                raise SystemExit(f"ERROR: {name} mux of stage {g} "
                                 f"(inst {side[g]}) has S on "
                                 f"ch[{inst[side[g]]['stage']}]")
    if len(inst) != 32:
        raise SystemExit(f"ERROR: {len(inst)} mux instances found, expected 32")

    # ---- physical positions from the .ext use lines (optional) ----
    pos = {}
    try:
        ext = args.pex.replace("arbchain_pex.spice", "extraction/arbchain.ext")
        for line in open(ext):
            m = re.match(r"^use sky130_fd_sc_hd__mux2_1 "
                         r"sky130_fd_sc_hd__mux2_1_(\d+)\s+"
                         r"(-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+)",
                         line)
            if m:
                ni = int(m.group(1))
                tx, ty = int(m.group(4)), int(m.group(7))
                # internal unit = 5 nm (2 units/lambda, lambda=0.01 um);
                # row pitch 920 units = 4.6 um
                pos[ni] = {"x_um": round(tx * 0.005, 3),
                           "row": (ty - 48) // 920}
    except OSError:
        pass

    stages = []
    for g in range(16):
        ti, bi = T[g], B[g]
        e = {"g": g, "top_inst": ti, "bot_inst": bi,
             "top_probe": probe[ti], "bot_probe": probe[bi],
             "top_x": f"sky130_fd_sc_hd__mux2_1_{ti}/X",
             "bot_x": f"sky130_fd_sc_hd__mux2_1_{bi}/X",
             "top_a0_gate": inst[ti]["a0_gate"],
             "top_a1_gate": inst[ti]["a1_gate"],
             "bot_a0_gate": inst[bi]["a0_gate"],
             "bot_a1_gate": inst[bi]["a1_gate"]}
        if pos:
            e["top_pos"] = pos.get(ti)
            e["bot_pos"] = pos.get(bi)
        stages.append(e)

    out = {"stages": stages,
           "arbiter": {"d_pin": DFF + "D.t1", "gate_pin": DFF + "GATE.t1",
                       "q": "q", "launch": "launch"}}
    with open(args.output, "w") as f:
        json.dump(out, f, indent=1)

    print(f"chain map OK: 32 muxes, D<-inst {anchor['D']}, "
          f"GATE<-inst {anchor['GATE']}")
    for e in stages:
        tp = e.get("top_pos") or {}
        bp = e.get("bot_pos") or {}
        print(f"  stage {e['g']:2d}: top=inst {e['top_inst']:2d} "
              f"(x={tp.get('x_um', '?')}, row={tp.get('row', '?')})  "
              f"bot=inst {e['bot_inst']:2d} "
              f"(x={bp.get('x_um', '?')}, row={bp.get('row', '?')})")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
