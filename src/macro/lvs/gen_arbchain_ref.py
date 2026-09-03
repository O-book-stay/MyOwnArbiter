#!/usr/bin/env python3
# ============================================================
# Generate the LVS reference (schematic) netlist for the
# `arbchain` hard macro (src/macro/arbchain.gds).
#
# Sources of truth -- the stale generators (gen_arbchain.py,
# my_own_arbchain.gds, arbchain_v2.gds, arbchain_noobs.lef,
# arbchain_extracted.cir) are intentionally NOT consulted:
#   - src/macro/arbchain.lef      macro interface (MACRO, SIZE, PIN set)
#   - src/puf_defines.v           ARB_STAGES
#   - src/arbiter_chain.v (+ arb_mux.v, arbiter_cell.v)  topology
#   - PDK sky130_fd_sc_hd.spice   cell pin order (parsed at runtime)
#
# Encoded topology (from arbiter_chain.v, stage g in [0, ARB_STAGES)):
#   top[0] = bot[0] = launch
#   top_mux:  X = S ? A1 : A0  with A0=top[g], A1=bot[g], S=ch[g] -> top[g+1]
#   bot_mux:  X = S ? A1 : A0  with A0=bot[g], A1=top[g], S=ch[g] -> bot[g+1]
#   arbiter (dfrtp_1, async active-low reset): D=top[N], CLK=bot[N],
#   RESET_B=arb_rst_n, Q=q
#
# Usage: python3 gen_arbchain_ref.py -o <out.spice>
# ============================================================

import argparse
import glob
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
LEF = os.path.join(REPO, "src", "macro", "arbchain.lef")
DEFINES = os.path.join(REPO, "src", "puf_defines.v")

MUX = "sky130_fd_sc_hd__mux2_1"
DFF = "sky130_fd_sc_hd__dfrtp_1"

# interface expected from arbchain.lef: (DIRECTION, USE)
EXP_PINS = {}
for _i in range(16):
    EXP_PINS[f"ch[{_i}]"] = ("INPUT", "SIGNAL")
EXP_PINS["launch"] = ("INPUT", "SIGNAL")
EXP_PINS["arb_rst_n"] = ("INPUT", "SIGNAL")
EXP_PINS["q"] = ("OUTPUT", "SIGNAL")
EXP_PINS["VPWR"] = ("INOUT", "POWER")
EXP_PINS["VGND"] = ("INOUT", "GROUND")

EXP_MUX_PINS = {"A0", "A1", "S", "X", "VPWR", "VGND", "VPB", "VNB"}
EXP_DFF_PINS = {"D", "CLK", "RESET_B", "Q", "VPWR", "VGND", "VPB", "VNB"}


def parse_lef(path):
    macro = None
    size = None
    pins = []  # (name, direction, use) in LEF order
    cur = None
    cur_dir = None
    cur_use = None
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith("MACRO "):
                macro = s.split()[1]
            elif s.startswith("SIZE ") and macro:
                m = re.match(r"SIZE\s+([\d.]+)\s+BY\s+([\d.]+)\s*;", s)
                size = (float(m.group(1)), float(m.group(2)))
            elif s.startswith("PIN ") and cur is None:
                cur = s.split()[1]
                cur_dir = None
                cur_use = None
            elif cur is not None:
                if s.startswith("DIRECTION "):
                    cur_dir = s.split()[1]
                elif s.startswith("USE "):
                    cur_use = s.split()[1]
                elif s == f"END {cur}":
                    pins.append((cur, cur_dir, cur_use))
                    cur = None
    return macro, size, pins


def parse_stages(path):
    with open(path) as f:
        txt = f.read()
    m = re.search(r"^\s*`define\s+ARB_STAGES\s+(\d+)", txt, re.M)
    if not m:
        sys.exit(f"ERROR: ARB_STAGES not found in {path}")
    return int(m.group(1))


def find_pdk_spice():
    pats = [
        os.path.expanduser(
            "~/.ciel/ciel/sky130/versions/*/sky130A/libs.ref/"
            "sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"
        ),
        "/usr/local/share/pdk/*/sky130A/libs.ref/sky130_fd_sc_hd/spice/"
        "sky130_fd_sc_hd.spice",
    ]
    for pat in pats:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    sys.exit("ERROR: sky130_fd_sc_hd.spice not found (use --pdk-spice)")


def parse_subckt(path, cell):
    """Return the pin list of `.subckt <cell> ...` (continuations joined)."""
    with open(path) as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        s = line.strip()
        m = re.match(r"^\.subckt\s+(\S+)\s*(.*)$", s, re.I)
        if m and m.group(1) == cell:
            pins = m.group(2).split()
            j = i + 1
            while j < len(lines) and lines[j].startswith("+"):
                pins += lines[j].lstrip("+").split()
                j += 1
            return pins
    sys.exit(f"ERROR: .subckt {cell} not found in {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--pdk-spice", default=None,
                    help="path to sky130_fd_sc_hd.spice (default: autodetect)")
    args = ap.parse_args()

    macro, size, pins = parse_lef(LEF)
    assert macro == "arbchain", f"LEF MACRO is {macro!r}, expected 'arbchain'"

    got = {n: (d, u) for n, d, u in pins}
    if got != EXP_PINS:
        missing = sorted(set(EXP_PINS) - set(got))
        extra = sorted(set(got) - set(EXP_PINS))
        wrong = sorted(n for n in set(got) & set(EXP_PINS) if got[n] != EXP_PINS[n])
        sys.exit(f"ERROR: arbchain.lef pin interface mismatch: "
                 f"missing={missing} extra={extra} wrong-attrs={wrong}")
    if len(pins) != len(EXP_PINS):
        sys.exit(f"ERROR: duplicate pins in LEF ({len(pins)} entries)")
    print(f"LEF OK: {macro}  SIZE {size[0]} x {size[1]} um, {len(pins)} pins")

    stages = parse_stages(DEFINES)
    if stages != 16:
        sys.exit(f"ERROR: ARB_STAGES={stages}, the physical macro has 16 stages")
    print(f"ARB_STAGES = {stages} (src/puf_defines.v)")

    pdk = args.pdk_spice or find_pdk_spice()
    mux_pins = parse_subckt(pdk, MUX)
    dff_pins = parse_subckt(pdk, DFF)
    if set(mux_pins) != EXP_MUX_PINS:
        sys.exit(f"ERROR: {MUX} pins {sorted(mux_pins)} != {sorted(EXP_MUX_PINS)}")
    if set(dff_pins) != EXP_DFF_PINS:
        sys.exit(f"ERROR: {DFF} pins {sorted(dff_pins)} != {sorted(EXP_DFF_PINS)}")
    print(f"PDK OK: {MUX} {' '.join(mux_pins)}")
    print(f"PDK OK: {DFF} {' '.join(dff_pins)}")

    pg = {"VPWR": "VPWR", "VGND": "VGND", "VPB": "VPWR", "VNB": "VGND"}

    def mux_inst(name, side, g):
        a0 = "launch" if g == 0 else f"top[{g}]"
        b0 = "launch" if g == 0 else f"bot[{g}]"
        if side == "top":
            sig = {"A0": a0, "A1": b0, "S": f"ch[{g}]", "X": f"top[{g + 1}]"}
        else:
            sig = {"A0": b0, "A1": a0, "S": f"ch[{g}]", "X": f"bot[{g + 1}]"}
        netmap = {**sig, **pg}
        nets = " ".join(netmap[p] for p in mux_pins)
        return f"X{name} {nets} {MUX}", sig

    body = []
    n_mux = 0
    for g in range(stages):
        inst, _ = mux_inst(f"top_{g:02d}", "top", g)
        body.append(inst)
        n_mux += 1
        inst, _ = mux_inst(f"bot_{g:02d}", "bot", g)
        body.append(inst)
        n_mux += 1

    dff_netmap = {
        "D": f"top[{stages}]", "CLK": f"bot[{stages}]",
        "RESET_B": "arb_rst_n", "Q": "q", **pg,
    }
    body.append(
        f"Xarb {' '.join(dff_netmap[p] for p in dff_pins)} {DFF}"
    )

    ports = [n for n, _, _ in pins]
    n_int = 1 + 2 * stages  # launch + top[1..N] + bot[1..N]
    with open(args.output, "w") as f:
        f.write("* arbchain LVS reference (schematic) netlist\n")
        f.write("* generated by src/macro/lvs/gen_arbchain_ref.py\n")
        f.write("* interface: src/macro/arbchain.lef (pin order preserved)\n")
        f.write(f"* topology:  src/arbiter_chain.v, ARB_STAGES={stages}\n")
        f.write(f"* cells:     {pdk}\n")
        f.write(f".SUBCKT arbchain {' '.join(ports)}\n")
        for b in body:
            f.write(b + "\n")
        f.write(".ENDS arbchain\n")

    assert n_mux == 32 and stages == 16
    print(f"wrote {args.output}: {n_mux} x {MUX} + 1 x {DFF}, "
          f"{len(ports)} ports, {n_int} internal signal nets")


if __name__ == "__main__":
    main()
