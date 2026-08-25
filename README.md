![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Arbiter PUF

A challenge-response PUF design for Tiny Tapeout.

- [Read the documentation for the project](docs/info.md)

- Parallel 16-bit challenge: `{ui_in, uio_in}`; a new (different) bus
  value starts the next measurement, pulse `rst_n` to repeat one
- UART TX 115200 8N1 on `uo[0]`: response = 4 hex chars
- LEDs: `uo[1]` red, `uo[2]` green, `uo[3]` blue

Run tests with `make -C test`.
