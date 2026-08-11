# Arbiter PUF (tt_um_obookstay_puf)

An **iterative-feedback arbiter strong PUF** for Tiny Tapeout, hybridised with a
silicon power-up flip-flop entropy bank.

- Challenge: 32 hex chars (128 bits) over UART (115200 8N1)
- Response: 128-bit hex string (32 chars) over UART
- Primary entropy: 48-stage arbiter switch chain raced by a launch edge,
  majority-voted 3x per bit, preserved through synthesis with `(* keep *)`
  attributes and `src/config.json` LibreLane settings
  (`SYNTH_KEEP_HIERARCHY_MODULES`, `SYNTH_SHARE_RESOURCES=false`,
  `SYNTH_STRATEGY=DELAY`)
- Hybrid anchor: an uninitialised power-up flip-flop bank (`silicon_entropy.v`)
  XORed into the RO signature, so the chip still has physical entropy even if
  the race turns out biased
- Response obfuscation: LFSR keystream XOR mixing

## Pinout

| Pin   | Function                    |
|-------|-----------------------------|
| ui[0] | UART RX (115200 8N1)        |
| uo[0] | UART TX (115200 8N1)        |
| uo[1] | LED R (measurement)         |
| uo[2] | LED G (race/sending)        |
| uo[3] | LED B (waiting for challenge) |

## How to test

1. Send a 32-hex-char challenge (e.g. `0123456789ABCDEF0123456789ABCDEF`) on
   `ui[0]` at 115200 8N1.
2. The design replies with the 128-bit response as 32 hex chars on `uo[0]`.
3. A second challenge triggers a second response.

Run the cocotb tests with `make -C test`.

## Notes for a paper

The gate-level netlist and STA reports from the GDS build can be used to
verify that the arbiter chain survives synthesis (96 muxes: 2 paths x 48
stages) and to extract the post-layout delay difference between the two race
paths.
