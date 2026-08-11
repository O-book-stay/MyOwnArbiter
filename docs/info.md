## How it works

An iterative-feedback arbiter strong PUF. A 32-hex-char challenge is folded
into an LFSR seed; a rising `launch` edge races down a 48-stage mux chain
(`arbiter_chain.v`, two balanced paths preserved with `(* keep *)` nets and
`SYNTH_KEEP_HIERARCHY_MODULES` in `src/config.json`), and `arbiter_cell.v`
latches which path arrives first. Each response bit is majority-voted over 3
races, then the trajectory is obfuscated with an LFSR keystream.

The hybrid anchor `silicon_entropy.v` is a bank of uninitialised flip-flops
that power up in a random-but-stable state on silicon (power-up PUF); it is
XORed into the RO signature so physical entropy is guaranteed even if the race
is biased. The response is sent as 32 hex chars over UART at 115200 baud on a
48 MHz clock.

## How to test

Hold `rst_n` low, then release it with `ena` high. Send a 32-hex-char
challenge on `ui[0]` (UART RX, 115200 8N1). The design replies with the
128-bit response as 32 hex chars on `uo[0]` (UART TX). LEDs: `uo[1]` red
(measurement), `uo[2]` green (race / sending), `uo[3]` blue (waiting for a
challenge).

## External hardware

A USB-UART adapter or host running at 115200 8N1, connected to `ui[0]` and
`uo[0]`.
