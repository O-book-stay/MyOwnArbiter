# DRC / CI failure analysis (2026-08-26)

Full diagnosis of the physical-design and CI failures blocking Tiny Tapeout
submission, with evidence. Goal: **pass TT precheck and gl_test, then tape
out** (decided 2026-08-26).

## Evidence base

- Local hardening run `runs/wokwi/` (2026-08-26 02:19–02:21, commit state
  between b03c59a and ef271bc).
- CI run
  [gds #39](https://github.com/O-book-stay/MyOwnArbiter/actions/runs/32883755918)
  on `ef271bc` (the current HEAD).
- Rule decks read directly from the PDK
  (`~/.ciel/.../sky130A/libs.tech/{klayout/drc/sky130A.lydrc,
  magic/sky130A.tech}`).
- Timeline: b19023e 00:24 (hand-drawn `arbchain.gds`) → b03c59a 01:14 (DRC
  gating relaxed) → local run 02:19 → ef271bc 02:26 → CI 02:26. The user's
  standalone KLayout DRC on `arbchain.gds` (09:45, `src/macro/sky130_drc.txt`)
  contains **zero** violation items — same file the flow consumed.

## What is already clean (local run, all corners)

LVS (0 diffs), timing (setup/hold WNS = 0), antenna (0), IR drop (worst
0.11 mV), PDN connectivity (PSM-0040, all shapes connected). The macro power
connection problem from the Discord thread is **solved** (custom
`src/pdn_cfg.tcl`, met2/met1→met4 `add_pdn_connect`, macro intersecting the
met4 straps). Root-level `pdn_*.def/.rpt` files are stale debug artifacts of
that effort.

## CI run #39 (ef271bc)

| Job      | Result | Notes |
|----------|--------|-------|
| gds      | pass   | flow completes (gating relaxed) |
| viewer   | pass   | |
| precheck | **fail** | Magic DRC ❌ + KLayout BEOL ❌ (67 violations); everything else ✅ (Pin, Boundary, Power pin, Layer, Cell name, FEOL, offgrid, zero-area, label overlap, urpm/nwell, analog, verilog syntax) |
| gl_test  | **fail** | compiles now; cocotb test dies on X |

ef271bc's three fixes are verified in-repo and worked: `arbchain.nl.v`
multi-line (was one line → "Unknown module type: arbchain"), `test/tb.v`
without power ports (matches the LibreLane 3.x top netlist),
`MAGIC_ZEROIZE_ORIGIN: false` (pin/boundary checks now pass — do not
re-enable).

## The 934 Magic DRC violations (local run, `runs/wokwi/62-magic-drc`)

All coordinates fall inside/around the hard macro (macro at x=83.30, y=7.20,
size 17.28 x 78.68 um):

| Count | Rule | Location (abs um) | Root cause |
|------:|------|-------------------|------------|
| 303 | LU.3 (P-diff to N-tap ≥ 15 um) | x[83.4,94.5] y[8.9,83.5] | no tapcells inside the hand-drawn macro |
| 269 | LU.2 (N-diff to P-tap ≥ 15 um) | x[83.4,94.5] y[7.7,81.9] | same |
| 151 | met2.2 (spacing < 0.14) | x[83.74,84.16] y[8.76,78.94] (local x 0.44–0.86, full height) | router met2 wires in the macro's open met2 window (LEF OBS starts at x=0.6/6.6) vs ch[] pin stubs / OBS corners |
| 128 | mcon.2 (spacing < 0.19) | x[85.17,92.72] y[9.89,79.10] | **unattributed** — see below |
| 34 | met3.2 (spacing < 0.30) | x[83.13,83.50] y[15.52,28.39] | router wires at the left pin slot — cluster starts 0.17 um **outside** the macro edge (83.30), so top-level routing is involved |
| 33 | nwell.4 (nwell without metal-connected N+ tap) | spread | 33 = exactly the instance count (32x mux2_1 + 1x dlrtp_1): every cell's isolated nwell lacks a tap |
| 12 | subcell abut/overlap | x[99.5,100.4] y[85.25,85.83] (top rail band) | drawn shapes vs mux/latch cell shapes across subcell boundaries (Magic hierarchy-only rule) |
| 4 | via.5a/4a (m1 overlap of via1 ≥ 0.06 one direction) | x[89.0,89.4] y[79.6,79.7] | pad/via overlap exactly 0.055 — passes KLayout, fails Magic (see deck table) |

Plus **2 routing DRC** (`44-openroad-detailedrouting`): met4 spacing,
`net:u_puf_top.launch` vs `inst:u_chain`, at (88.05–88.15) and (88.45–88.55),
y 7.2–7.92 = local x 4.75–4.85 / 5.15–5.25 — exactly the edges of the met4
OBS corridor gap [4.75, 5.25] (`gen_lef_gds.py` OLD_OBS) where the router
reaches the `launch` pin (LEF rect 4.830–5.170, y 0–0.72).

## Why KLayout showed 0 errors on the same GDS

The KLayout `sky130A.lydrc` deck and the Magic deck are **different rule
sets**. Magic is the signoff deck (used by LibreLane's DRC step and by TT
precheck). Verified facts:

| Rule class | Magic deck | KLayout deck |
|------------|-----------|--------------|
| LU.2/LU.3 latchup distance | present | **absent** (no LU rules at all) |
| nwell.4 (well tap) | present | **explicitly commented out** ("# rule nwell.4 is suitable for digital cells") |
| subcell abut/overlap | present (hierarchical rule) | no such concept |
| via.4a/5a (m1 overlap of 0.15 via1) | ≥ 0.06 one direction (tech line 4637, surround 30 directional) | `via.4a` ≥ 0.055 (lydrc line 507) → 0.26 pad over 0.15 via passes KLayout at exactly 0.055, fails Magic by 5 nm |
| mcon.2 spacing | 0.19 (tech line 4598) | `ct.2` 0.19 (lydrc line 461) — **same value** |

(Magic report numbers are scalefactor-5: "38"=0.19, "28"=0.14, "60"=0.30,
"6"=0.06.)

Consequence: 617/934 (LU + nwell.4 + abut) are **invisible to KLayout by
construction**; ~185 (met2.2/met3.2 + the 2 met4) are **in-context** violations
that a standalone macro DRC can never see (router wires). The 4 via.5a are a
threshold-boundary divergence. **All macro DRC iteration must be done against
Magic**, not KLayout.

## Open: mcon.2 (128)

Both decks use 0.19 um, so deck coverage does not explain why the standalone
KLayout run reported none. Candidates: hand-drawn mcon vs cell-internal mcon
pairs (< 0.19 apart), engine semantics (touching/corner handling), or
flow-induced geometry. **Phase A** (Magic DRC on the standalone macro in
docker) will attribute these definitively.

## Open: KLayout BEOL 67 (TT precheck)

The standalone macro is KLayout-clean, so all 67 BEOL violations on the final
tile involve top-level-added geometry (router/PDN vs macro windows) — the same
class as Magic's met2.2/met3.2/met4 items. Report is in the CI
`precheck_reports` artifact; to be attributed locally (run the BEOL deck on
the re-hardened GDS).

## gl_test failure (CI, exit 2)

Compile is fixed (ef271bc). The cocotb test `test_puf_roundtrip` fails at
380 ns: `test.py:35` does `int(dut.uo_out.value)` and the vector contains X.

Traced so far:

- `uo_out[3:0]` = uart_tx / led_r / led_g / led_b (`tt_um_obookstay_puf.v:57-60`);
  `[7:4]` are conb constants.
- All controller/uart/lfsr registers have async resets
  (`puf_controller.v:165+`, `uart_tx.v:26+`, `lfsr.v:51+`).
- Prime suspect: `puf_top.v:131` `assign led_g = race_active ? arb_q :
  led_g_ctrl;` — **arb_q is exposed on uo_out[2] during races**, and the
  failure timestamp coincides with the first race starting.
  `arb_q` is already preserved from pruning by `(* keep *)` (`puf_top.v:29`),
  so the mirror may be redundant.
- Static analysis says the GL chain should be deterministic (both paths seeded
  from `launch`, `ch` from the reset-loaded LFSR), so the X is likely a
  transient/scheduling artifact — **unconfirmed**.

Fix options (after waveform confirms which bit/driver):
1. `test.py`: sample only `uo_out[0]` (only bit 0 is used anyway; `int()` on
   the whole vector dies if any bit is X).
2. RTL: drop or gate the `led_g` mirror.
3. If `arb_q` itself is persistently X: arbchain GL simulation model issue —
   separate fix.

The CI artifact `gatelevel_test_results` contains `tb.fst` for the waveform.

## Plan (agreed 2026-08-26)

Constraints from the owner:
- The **hand-drawn GDS is the base** (`my_own_arbchain.gds` →
  `fix_my_own_arbchain.py` → `arbchain.gds`); `gen_arbchain.py`'s signal
  routing was abandoned (it could not route the signals correctly). New work
  goes into a **refine** tool that modifies DRC issues on top of the
  hand-drawn geometry without touching signal routing.
- Taps go into the existing footprint (no TW widening) to keep the PDN
  contract (met4 OBS+halo edge 94.88 < strap obstruction 95.72, MACRO_X
  83.30) untouched.

- **Phase A (attribution, read-only)**: geometry inventory of the hand-drawn
  GDS (KLayout script); Magic DRC baseline on the standalone macro in the
  LibreLane docker (splits intrinsic vs in-context; settles mcon.2); KLayout
  BEOL run on the final GDS (attributes the 67).
- **Phase B (`src/macro/refine_arbchain.py`)**: fix on top of the hand-drawn
  GDS — enlarge the 4 via1 pads (+5 nm); delete/stagger redundant parallel
  mcons (< 0.38 apart) keeping connectivity (verify with netgen LVS +
  `probe_short.py`/`probe_netfail.py`); fix the met2 strip spacing; taps:
  n-well merge strips in the middle gap (x 4.14–7.14, ~1.2 um free slot
  between the met1 straps) so the 33 isolated nwells merge, + tap column;
  NOTE a corridor-only tap fixes LU distances but NOT nwell.4 (tap nwell must
  be inside/merged with each cell's nwell — depends on whether cell nwells
  reach the cell edge, verify in Phase A); flatten subcells on export (kills
  the 12 abut violations); widen the ch[]/arb_rst_n pin landing slots and/or
  extend pin stubs (fixes met2.2/met3.2 and the 2 met4 routing DRCs). Update
  `gen_lef_gds.py` ports/OBS afterwards and re-validate the PDN contract.
- **Phase C**: `--create-user-config` + `--harden` at HEAD (the local
  `runs/wokwi/final` GDS predates ef271bc's origin fix); targets
  `route__drc_errors=0`, `magic__drc_error__count=0`; smoke test in docker;
  reproduce TT precheck + gl_test locally before pushing.
- **Phase D**: cleanup (root `pdn_*.def/.rpt`, `===)EOF~/` junk dir,
  `test/a.out`), README "Known DRC issues" section update, keep AGENTS.md in
  sync.

## Misc facts worth remembering

- `timing__drv__floating__nets = 2` in the final metrics — unidentified,
  benign so far (floating pins = 0).
- The macro `.lib` has no timing arcs (blackbox); STA treats the arbiter as
  zero-delay. 36 unannotated nets (filtered to 0) come from the macro having
  no SPEF.
- `DRC_EXCLUDE_CELLS: ["arbchain"]` + `ERROR_ON_MAGIC_DRC/TR_DRC: false`
  currently relax gating (b03c59a) — the goal is 0 violations so precheck
  passes regardless.
- `AGENTS.md` previously said ARB_STAGES=29 / macro 103.98 um — stale since
  the 16-stage reduction (now `puf_defines.v:26`, macro 17.28 x 78.68 um).
