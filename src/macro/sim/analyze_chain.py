#!/usr/bin/env python3
# ============================================================
# Turn the per-node .meas results of the arbchain post-layout runs
# into the per-stage race-skew table (the 16 w's) and diagnose WHERE
# the systematic top-vs-bot asymmetry lives.
#
# Model (src/arbiter_chain.v convention):
#   S(g)  = t(top[g]) - t(bot[g])          arrival skew at node g
#   c_g=0: S(g+1) = S(g) + a_g             a_g = straight-path skew of stage g
#   c_g=1: S(g+1) = -S(g) + b_g            b_g = crossed-path skew of stage g
#   => S(16) = SUM_g (c_g==0 ? a_g : b_g) * phi_g,
#      phi_g = prod_{j=g+1..15} (-1)^{c_j}
#
# For an antisymmetric (mirror) stage a_g = -b_g and the classic
# linear model is w_g = (a_g - b_g)/2; (a_g + b_g)/2 is the residual.
#
# Each a_g/b_g is further split into input-wire vs cell+output-net
# using the gate-side probes, so a large term can be attributed to
# the inter-stage wiring (the met3/met4 crossovers) or to a mux row.
#
# Usage:
#   python3 analyze_chain.py --map chain_map.json \
#       --log 0000=postsim_0000.log --log ffff=postsim_ffff.log \
#       [--log a5a5=postsim_a5a5.log] [--out chain_diag.txt]
# ============================================================

import argparse
import json
import re

RE_MEAS = re.compile(r"^\s*([A-Za-z]\w*)\s*=\s*([-+0-9.eE]+)\s*$")


def parse_log(path):
    vals = {}
    for raw in open(path):
        m = RE_MEAS.match(raw)
        if m:
            vals[m.group(1).lower()] = float(m.group(2))  # ngspice lowercases
    return vals


def S(tT, tB, g):
    return tT[g] - tB[g]


def need(d, name, hx):
    key = name.lower()
    if key not in d:
        raise SystemExit(f"ERROR: meas '{name}' missing/failing in the "
                         f"{hx} log")
    return d[key]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--log", action="append", required=True,
                    help="HEX=path-to-log (repeatable)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    amap = json.load(open(args.map))
    logs = {}
    for spec in args.log:
        hx, path = spec.split("=", 1)
        logs[hx.lower()] = parse_log(path)
    if "0000" not in logs or "ffff" not in logs:
        raise SystemExit("need at least --log 0000=... and --log ffff=...")

    def series(d, hx, prefix):
        return {g: need(d, f"{prefix}{g:02d}", hx) for g in range(1, 17)}

    def gates(d, hx, side, pin):
        return {g: need(d, f"w{side}{pin}{g:02d}", hx)
                for g in range(16)}

    out_lines = []
    say = lambda s="": (out_lines.append(s), print(s))

    a = b = None
    for hx, d in sorted(logs.items()):
        tT = series(d, hx, "tT")
        tB = series(d, hx, "tB")
        c = int(hx, 16)
        Sv = {0: 0.0}          # top[0] = bot[0] = launch -> zero skew
        Sv.update({g: S(tT, tB, g) for g in range(1, 17)})
        say(f"== challenge 0x{hx}: S(16) = {Sv[16] * 1e12:+.2f} ps  "
            f"(q: qval={d.get('qval')}, tq={d.get('tq')})")
        if hx == "0000":
            a = {g: Sv[g + 1] - Sv[g] for g in range(16)}
        elif hx == "ffff":
            b = {g: Sv[g + 1] + Sv[g] for g in range(16)}

    # ---- per-stage decomposition ----
    # Both splits come from the 0000 run: the A0/A1 gate probes sit on the
    # same physical wires in every challenge (the select does not change
    # wiring), and in 0000 the accumulated skew S(g) stays small - in the
    # ffff run it alternates and grows to +-13 ps, which would leak into
    # the gate-arrival differences and pollute the split.
    d0, df = logs["0000"], logs["ffff"]
    tT0, tB0 = series(d0, "0000", "tT"), series(d0, "0000", "tB")
    tTf, tBf = series(df, "ffff", "tT"), series(df, "ffff", "tB")
    A0T, A1T = gates(d0, "0000", "T", "A0"), gates(d0, "0000", "T", "A1")
    A0B, A1B = gates(d0, "0000", "B", "A0"), gates(d0, "0000", "B", "A1")
    tL0 = need(d0, "tL", "0000")

    say()
    say("per-stage skew decomposition (ps; + means the TOP path is slower):")
    say("  g  straight a_g = wire + cell      crossed b_g = wire + cell"
        "      w_g=(a-b)/2  resid=(a+b)/2")
    worst = []
    for g in range(16):
        # straight: top mux fed by top[g] via A0; bot mux fed by bot[g] via A0
        srcT = tL0 if g == 0 else tT0[g]
        srcB = tL0 if g == 0 else tB0[g]
        a_wire = (A0T[g] - srcT) - (A0B[g] - srcB)
        a_cell = a[g] - a_wire
        # crossed: top mux fed by bot[g] via A1; bot mux fed by top[g] via A1
        # (same physical wires in every challenge -> use the 0000 arrivals)
        cT = tL0 if g == 0 else tT0[g]
        cB = tL0 if g == 0 else tB0[g]
        b_wire = (A1T[g] - cB) - (A1B[g] - cT)
        b_cell = b[g] - b_wire
        wg = (a[g] - b[g]) / 2
        rg = (a[g] + b[g]) / 2
        say(f"  {g:2d}      {a[g] * 1e12:+7.2f} = {a_wire * 1e12:+6.2f} "
            f"+ {a_cell * 1e12:+6.2f}        {b[g] * 1e12:+7.2f} = "
            f"{b_wire * 1e12:+6.2f} + {b_cell * 1e12:+6.2f}"
            f"      {wg * 1e12:+7.2f}    {rg * 1e12:+7.2f}")
        worst.append((abs(wg), g, a[g], b[g], a_wire, a_cell, b_wire, b_cell))

    say()
    sum_a = sum(a.values()) * 1e12
    sum_b = sum(b.values()) * 1e12
    say(f"checks: sum a_g = {sum_a:+.2f} ps (S16@0000 = "
        f"{(tT0[16] - tB0[16]) * 1e12:+.2f}); "
        f"alt sum b_g*(-1)^(15-g) = "
        f"{sum(b[g] * (-1) ** (15 - g) for g in range(16)) * 1e12:+.2f} ps "
        f"(S16@ffff = {(tTf[16] - tBf[16]) * 1e12:+.2f})")

    # last-stage wire (mux output -> dlrtp pin)
    lw0 = (need(d0, "tDpin", "0000") - tT0[16]) - \
          (need(d0, "tGpin", "0000") - tB0[16])
    lwf = (need(df, "tDpin", "ffff") - tTf[16]) - \
          (need(df, "tGpin", "ffff") - tBf[16])
    say(f"last-stage wire to dlrtp (D vs GATE): {lw0 * 1e12:+.3f} ps "
        f"@0000, {lwf * 1e12:+.3f} ps @ffff")

    # ---- prediction vs measurement on any extra challenge ----
    for hx, d in sorted(logs.items()):
        if hx in ("0000", "ffff"):
            continue
        c = int(hx, 16)
        pred = 0.0
        for g in range(16):
            phi = 1.0
            for j in range(g + 1, 16):
                if (c >> j) & 1:
                    phi = -phi
            pred += (a[g] if (c >> g) & 1 == 0 else b[g]) * phi
        tT, tB = series(d, hx, "tT"), series(d, hx, "tB")
        meas = (tT[16] - tB[16]) * 1e12
        q_meas = d.get("qval")
        q_pred = 1.8 if meas > 0 else 0.0
        say(f"predict-check 0x{hx}: S16 predicted {pred * 1e12:+.2f} ps, "
            f"measured {meas:+.2f} ps, q predicted {q_pred:.1f} "
            f"measured {q_meas}")

    worst.sort(reverse=True)
    say()
    say("worst stages by |w_g|:")
    for aw, g, *_ in worst[:5]:
        say(f"  stage {g:2d}: |w| = {aw * 1e12:.2f} ps "
            f"(a={a[g] * 1e12:+.2f}, b={b[g] * 1e12:+.2f})")

    if args.out:
        with open(args.out, "w") as f:
            f.write("\n".join(out_lines) + "\n")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
