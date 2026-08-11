# Arbiter PUF

A challenge-response PUF design for Tiny Tapeout.

- UART 115200 8N1: `ui[0]` RX, `uo[0]` TX
- Send a 32-hex-char challenge, receive a 128-bit hex response
- LEDs: `uo[1]` red, `uo[2]` green, `uo[3]` blue

Run tests with `make -C test`.
