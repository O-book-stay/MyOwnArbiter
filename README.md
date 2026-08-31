![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Simple 8-bit Multicycle CPU

A tiny 8-bit multicycle CPU for Tiny Tapeout with a UART program loader.

- [Read the documentation for the project](docs/info.md)

- UART 115200 8N1: `ui[0]` RX, `uo[0]` TX
- Boot protocol: send `'L'`, length, program bytes, then `'R'` to run
- GPIO output register on `uio[7:0]` (memory-mapped at `0xFC`)
- LEDs: `uo[1]` red (boot), `uo[2]` green (running), `uo[3]` blue (halted)

Run tests with `make -C test`, or the plain-iverilog smoke bench:

```
cd test
iverilog -g2012 -s tb_smoke_cpu -I../src tb_smoke_cpu.v \
  ../src/cpu_defines.v ../src/cpu_core.v ../src/cpu_top.v \
  ../src/uart_rx.v ../src/uart_tx.v ../src/tt_um_obookstay_cpu.v
vvp a.out
```
