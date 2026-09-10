![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Arbiter PUF

A challenge-response arbiter strong PUF for Tiny Tapeout, hardened to a **1x1**
sky130A tile (`tt_um_obookstay_puf`).

## Overview

- Parallel **16-bit challenge** on `{ui_in, uio_in}`; a bus value **different**
  from the previously measured one starts the next measurement (pulse `rst_n`
  to re-run the same challenge).
- **Response = 4 hex chars** (the 16-bit response) over UART TX **115200 8N1**
  on `uo[0]`.
- Entropy comes from the hand-drawn, mirror-symmetric hard macro `arbchain`
  (16 switch stages), so the race is dominated by random process variation
  rather than systematic routing skew.
- Iterative-feedback architecture: a **bootstrap** phase (8 voted bits -> hidden
  seed) then a **main loop** (16 bits, 3-way majority vote per bit) whose LFSR
  state is folded back and mixed inline with the race bit.

The design is an iterative-feedback arbiter PUF: instead of one pass through the
switch chain, each response bit is the majority of several races whose
challenges are derived from the LFSR and the evolving hidden state, which
increases nonlinearity within a limited area.

## Interface

| Pin | Dir | Function |
|-----|-----|----------|
| `ui[7:0]`  | in  | Challenge bits 15..8 |
| `uio[7:0]` | in  | Challenge bits 7..0 |
| `uo[0]`    | out | UART TX (115200 8N1), 4 hex chars per measurement |
| `uo[1]`    | out | LED R - measurement in progress |
| `uo[2]`    | out | LED G - race/send activity (mirrors `arb_q` during a race) |
| `uo[3]`    | out | LED B - waiting for a new challenge |
| `uo[7:4]`  | out | 0 |

`challenge = {ui_in, uio_in}` (`ui[7]` = bit 15 ... `uio[0]` = bit 0). After
reset, the first measurement fires on any bus value; change the bus to a
different value to start the next one. `ena` gates the internal reset.

## RTL architecture

| Module | Role |
|--------|------|
| `tt_um_obookstay_puf` | Tiny Tapeout wrapper: challenge bus, UART/LED outputs |
| `puf_top` | Instantiates the chain, LFSR, UART and controller |
| `puf_controller` | FSM: challenge detect, bootstrap, race sequencing, vote, output mixing |
| `lfsr` | Challenge / keystream generation (response bits folded back) |
| `uart_tx` | 115200 8N1 transmitter for the 4-hex-char response |
| `arbchain` / `arbiter_chain` / `arbiter_cell` / `arb_mux` | Arbiter switch chain (behavioural model for RTL sim; hard macro on silicon) |

Per query the controller pulses `launch` into the chain; each stage is two 2:1
muxes that either pass straight or cross under the challenge bit. The arbiter
latch (`arbiter_cell`) samples which path arrives first. The voted bit is folded
back into the LFSR and mixed inline with the keystream and a challenge-parity
term; every 4 finished bits a hex char is sent on the UART.

## Design flow

### 1. RTL simulation

A cocotb bench runs two challenge/response rounds on the parallel bus and checks
that different challenges give different responses. A dependency-free
self-checking testbench (`test/tb_smoke.v`) performs the same two-round check
with cycle-exact UART timing.

### 2. `arbchain` hard macro

The arbiter switch chain is a hand-drawn hard macro (17.28 x 82.0 um) placed at
(40, 30) R90. Its two delay lines are laid out mirror-symmetrically about the
macro centreline so the race outcome reflects random process variation rather
than systematic asymmetry. Well taps (`src/macro/add_taps.py`) fix the
latch-up/well rules inside the footprint; the LEF (size, signal pins, met4 PG
bands) is maintained in sync with the GDS.

### 3. DRC / LVS

- **Macro:** standalone Magic DRC on `arbchain.gds` plus netgen LVS of the macro
  interior against a reference netlist generated from the LEF interface and RTL
  topology. The tile flow black-boxes the macro, so this standalone step is what
  actually verifies its wiring. Result: **LVS PASS** ("Circuits match uniquely");
  Magic DRC **0** after the well taps.
- **Tile:** LibreLane's signoff DRC/LVS, including the macro-to-PDN interface.

### 4. Place & route (PnR)

LibreLane hardens the tile for sky130A. The macro's met4 power bands are picked
up by the default PDN grid; timing (all corners), antenna, IR drop and PDN
connectivity sign off cleanly. A small set of context-only `met4.2` spacing
findings at the macro PDN vias is accepted.

### 5. Post-layout simulation

The macro is extracted with distributed R and substrate/coupling C (Magic
`extract` + `extresist`, `ext2spice extresist on`), then simulated in ngspice
with a single launch pulse per challenge. The chain topology is mapped
electrically, per-node arrival times are measured, and the results are reduced
to the per-stage race-skew table (the 16 `w` terms of the classic linear PUF
model). Challenges `0000` / `ffff` / `a5a5` are used, with the `a5a5` run acting
as a prediction check of the linear model. Findings: the chain RC slows the
arbiter edges to ~22 ps / 0.4 V, comparable to the race itself (2-14 ps), and
stage 15 carries the worst systematic term (the D-side wire into the arbiter
flop), while the inter-stage crossovers are mirror-matched to ~0.03 ps.

## Status

| Stage | Result |
|-------|--------|
| RTL simulation | Pass - two challenges produce different responses |
| Macro DRC | Pass - standalone Magic DRC 0 |
| Macro LVS | Pass - "Circuits match uniquely" |
| Tile DRC | 8 context-only `met4.2` findings, accepted |
| PnR (timing / antenna / IR / PDN) | Clean |
| Post-layout sim | Per-stage skew extracted; stage-15 asymmetry identified |
| Gate-level test | Open - `uo_out` X during a race |
