![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Arbiter PUF

A challenge-response PUF design for Tiny Tapeout.

- [Read the documentation for the project](docs/info.md)

- Parallel 16-bit challenge: `{ui_in, uio_in}`; a new (different) bus
  value starts the next measurement, pulse `rst_n` to repeat one
- UART TX 115200 8N1 on `uo[0]`: response = 4 hex chars
- LEDs: `uo[1]` red, `uo[2]` green, `uo[3]` blue

Run tests with `make -C test`.

## Known DRC issues

The tile hardens and routes successfully (LVS / setup / hold / antenna all
clean), but the flow reports a set of deferred DRC findings that are
accepted for this project (`ERROR_ON_MAGIC_DRC` / `ERROR_ON_TR_DRC` are
disabled in `src/config.json`; full reports stay in the GDS action
artifacts under `runs/wokwi/62-magic-drc/reports/`):

- **~600 LU.2/LU.3 + nwell.4**: well-tap distance inside the hand-drawn
  `arbchain` hard macro — the macro rows contain no tap cells. Latch-up
  risk is judged acceptable for this characterisation rig; fixing it
  means redrawing the macro with internal taps.
- **132 mcon.2/via.5a + 46 met3.2**: spacing inside/at the edge of the
  macro drawing.
- **151 met2.2**: PDN/routing environment near the macro halo.
- **2 met4 spacing** (routing DRC): at the macro power-pin ↔ PDN strap
  interface.

These are excluded from the design's DRC gating via
`DRC_EXCLUDE_CELLS: ["arbchain"]` plus the two error flags above.
