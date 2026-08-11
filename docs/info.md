## How it works

Challenge-response PUF over UART: a 32-hex-char challenge in, a 128-bit hex
response out (115200 8N1).

## How to test

Release reset, then send a 32-hex-char challenge on `ui[0]`. The response is
sent as 32 hex chars on `uo[0]`.

## External hardware

A USB-UART adapter or host at 115200 8N1.
