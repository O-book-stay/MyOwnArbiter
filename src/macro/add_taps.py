#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# add_taps.py -- add well taps to the hand-drawn arbchain macro (arbchain.gds).
#
# Fixes the 400 tap-related Magic DRCs (nwell.4 x33, LU.2 x96, LU.3 x271):
#   - 1 N+ tap per nwell patch (17 patches: 32 mux2 rows -> 16 merged patches
#     via a shared inter-column extension, plus the dlrtp patch), connected to
#     VPWR through mcon -> met1 stub -> strap-2 (x 5.765..6.035, traced VPWR).
#   - 1 P+ tap per row gap (16 gaps), connected to VGND through mcon ->
#     met1 stub -> strap-1 (x 4.815..4.985, traced VGND).
# Tap geometry is copied verbatim from sky130_fd_sc_hd__tapvpwrvgnd_1 slices
# (tap 65/44, licon 66/44, li1 67/20, mcon 67/44, nsdm 93/44, psdm 94/20,
# met1 stub 68/20, 78/44) so the local stack is proven DRC-clean.
#
# NOTE: operates directly on arbchain.gds (the user-maintained source; the
# stale my_own_arbchain.gds pipeline must NOT be re-run afterwards, it would
# drop the taps).  A backup arbchain.pre_taps.gds is written once.
#
# Usage (inside librelane container, /work = repo):
#   python3 /work/src/macro/add_taps.py
import os
import shutil
import sys

import klayout.db as pya

HERE = os.path.dirname(os.path.abspath(__file__))
GDS = os.path.join(HERE, "arbchain.gds")
BAK = os.path.join(HERE, "arbchain.pre_taps.gds")

PDK_CANDIDATES = [
    os.environ.get("TAP_PDK_GDS", ""),
    "/pdk/ciel/sky130/versions/8afc8346a57fe1ab7934ba5a6056ea8b43078e71/"
    "sky130A/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds",
    "/home/obooky/.ciel/ciel/sky130/versions/"
    "8afc8346a57fe1ab7934ba5a6056ea8b43078e71/sky130A/libs.ref/"
    "sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds",
]

TAP_CELL = "sky130_fd_sc_hd__tapvpwrvgnd_1"
COPY_LAYERS = [(65, 44), (66, 44), (67, 20), (67, 44),
               (93, 44), (94, 20), (68, 20), (78, 44)]
NWL = (64, 20)

# template frame: VGND rail centre y=0, VPWR rail centre y=2.72.
# slices split at y=1.10 (template empty between 0.975 and 1.25).
N_Y = (1.10, 3.00)
P_Y = (-0.35, 1.10)

# stamp offsets (um, on the 5 nm grid)
OX_N = 5.67          # N-tap slice centre lands on x=5.90 (strap-2 centre)
OX_P = 4.67          # P-tap slice centre lands on x=4.90 (strap-1 centre)
NWELL_EXT_RIGHT = 6.98   # col1 nwell patch 4.33 -> 6.98: encloses the N-tap
# and OVERLAPS the col2 patch (6.95..) so each row merges into one tapped
# nwell region (nwell.4 satisfied; no nwell.2a near-spacing is left behind).
# dlrtp left-side stamp: slice centre on x=2.08, tab joins user VPWR rail
OX_DL = 1.85
DL_TAB = (0.05, 2.48, 0.85, 3.06)   # relative to (OX_DL, oy): met1 tab
DL_EXT = (-0.19, 1.305, 0.61, 2.91)  # relative: nwell extension rect


def dbu(v):
    return int(round(v * 1000))


def main():
    pdk = next(p for p in PDK_CANDIDATES if p and os.path.exists(p))
    print("template:", pdk)

    ly = pya.Layout()
    ly.read(GDS)
    top = ly.top_cell()
    assert top.name == "arbchain", top.name
    if abs(ly.dbu - 0.001) > 1e-12:
        raise SystemExit(f"unexpected macro dbu {ly.dbu}")

    tap_li = ly.find_layer(65, 44)
    if tap_li is not None:
        it = top.begin_shapes_rec(tap_li)
        while not it.at_end():
            raise SystemExit("arbchain.gds already contains tap (65/44) shapes; "
                             "restore arbchain.pre_taps.gds first or use a fresh file")
        # (begin_shapes_rec iterator is empty when no shapes exist)

    tly = pya.Layout()
    tly.read(pdk)
    tcell = tly.cell(TAP_CELL)
    assert abs(tly.dbu - ly.dbu) < 1e-12, (tly.dbu, ly.dbu)

    # ---- extract template slices -------------------------------------------
    n_slice, p_slice = [], []
    for (ln, dn) in COPY_LAYERS:
        li = tly.layer(ln, dn)
        for s in tcell.shapes(li).each():
            if not (s.is_box() or s.is_polygon()):
                continue
            b = s.box
            in_n = b.bottom < dbu(N_Y[1]) and b.top > dbu(N_Y[0])
            in_p = b.bottom < dbu(P_Y[1]) and b.top > dbu(P_Y[0])
            assert not (in_n and in_p), f"shape crosses slice split: {ln}/{dn} {b}"
            if in_n:
                n_slice.append(((ln, dn), s))
            if in_p:
                p_slice.append(((ln, dn), s))

    def has(sl, ln, dn):
        return any(k == (ln, dn) for k, _ in sl)

    for sl, tag in ((n_slice, "N"), (p_slice, "P")):
        print(f"  {tag}-slice: {len(sl)} shapes")
    for k in [(65, 44), (66, 44), (67, 20), (67, 44), (68, 20)]:
        assert has(n_slice, *k) and has(p_slice, *k), f"missing {k}"
    assert has(n_slice, 93, 44), "N-slice lacks nsdm"
    assert has(p_slice, 94, 20), "P-slice lacks psdm"

    def stamp(sl, ox_um, oy_um):
        ox, oy = dbu(ox_um), dbu(oy_um)
        tr = pya.Trans(pya.Vector(ox, oy))
        for (ln, dn), s in sl:
            if s.is_box():
                out = s.box.transformed(tr)
            else:
                out = s.polygon.transformed(tr)
            top.shapes(ly.layer(ln, dn)).insert(out)

    # ---- collect rows -------------------------------------------------------
    mux_rows, dlrtp = [], None
    for inst in top.each_inst():
        d = inst.trans.disp
        if inst.cell.name == "sky130_fd_sc_hd__mux2_1":
            mux_rows.append(d.y)
        elif inst.cell.name == "sky130_fd_sc_hd__dlrtp_1":
            dlrtp = d.y
    assert dlrtp is not None and len(mux_rows) == 32
    mux_rows = sorted(set(mux_rows))
    assert len(mux_rows) == 16, mux_rows
    print(f"rows: {len(mux_rows)} mux2 + 1 dlrtp (y={dlrtp/1000:.2f})")

    # ---- stamps -------------------------------------------------------------
    n = p = 0
    for d in mux_rows:
        # N-tap between the columns, met1 stub onto strap-2 (VPWR)
        stamp(n_slice, OX_N, d / 1000.0)
        top.shapes(ly.layer(*NWL)).insert(pya.Box(
            dbu(4.33), d + dbu(1.305), dbu(NWELL_EXT_RIGHT), d + dbu(2.91)))
        n += 1
        # P-tap in the gap above this row, met1 stub onto strap-1 (VGND)
        stamp(p_slice, OX_P, d / 1000.0 + 3.28)
        p += 1

    # dlrtp: N-tap at the patch left edge, met1 tab joins the user VPWR rail
    ox, oy = OX_DL, dlrtp / 1000.0
    stamp(n_slice, ox, oy)
    top.shapes(ly.layer(*COPY_LAYERS[6])).insert(pya.Box(
        dbu(ox + DL_TAB[0]), dlrtp + dbu(DL_TAB[1]),
        dbu(ox + DL_TAB[2]), dlrtp + dbu(DL_TAB[3])))
    top.shapes(ly.layer(*NWL)).insert(pya.Box(
        dbu(ox + DL_EXT[0]), dlrtp + dbu(DL_EXT[1]),
        dbu(ox + DL_EXT[2]), dlrtp + dbu(DL_EXT[3])))
    n += 1

    print(f"stamps: N={n} P={p}")
    if not os.path.exists(BAK):
        shutil.copy(GDS, BAK)
        print("backup:", BAK)
    ly.write(GDS)
    print("wrote", GDS)


if __name__ == "__main__":
    sys.exit(main())
