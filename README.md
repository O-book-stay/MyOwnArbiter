![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Arbiter PUF

A challenge-response PUF design for Tiny Tapeout.

- [Read the documentation for the project](docs/info.md)

- UART 115200 8N1: `ui[0]` RX, `uo[0]` TX
- Send an 8-hex-char challenge, receive a 32-bit hex response
- LEDs: `uo[1]` red, `uo[2]` green, `uo[3]` blue

Run tests with `make -C test`.
