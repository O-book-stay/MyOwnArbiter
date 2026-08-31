## How it works

A simple 8-bit accumulator CPU (multi-cycle, custom instruction set) with
32 bytes of program/data RAM.  Programs are loaded over UART at boot:

```
'L' (0x4C)          start loading
<len> (1 byte)      program length N (1..32)
<N bytes>           program image, written to RAM starting at 0x00
'R' (0x52)          reset PC to 0 and run
```

The CPU starts in the boot state (LED R).  After `HALT` (or reset) a new
program can be loaded the same way.

### Registers

`A` (accumulator), `B`, `PC` (8-bit, wraps) and flags `Z` (zero) and `C`
(carry / no-borrow).

### Instruction set

All instructions are one byte, followed by one operand byte (`imm`/`addr`)
unless noted.  `mem` is the 32-byte RAM (0x00-0x1F).

| Opcode | Instr        | Effect                              | Flags |
|--------|--------------|-------------------------------------|-------|
| 0x00   | `NOP`        | do nothing                          |       |
| 0x10   | `LDI imm`    | A <- imm                            | Z     |
| 0x20   | `LDD addr`   | A <- mem[addr]                      | Z     |
| 0x30   | `STD addr`   | mem[addr] <- A                      |       |
| 0x40   | `ADDI imm`   | A <- A + imm                        | Z, C  |
| 0x50   | `ADDM addr`  | A <- A + mem[addr]                  | Z, C  |
| 0x60   | `SUBI imm`   | A <- A - imm                        | Z, C  |
| 0x70   | `SUBM addr`  | A <- A - mem[addr]                  | Z, C  |
| 0x80   | `ANDI imm`   | A <- A & imm                        | Z, C=0|
| 0x90   | `ORI imm`    | A <- A \| imm                       | Z, C=0|
| 0xA0   | `XORI imm`   | A <- A ^ imm                        | Z, C=0|
| 0xB0   | `MOV B,A`    | B <- A                              |       |
| 0xB8   | `MOV A,B`    | A <- B                              |       |
| 0xC0   | `JMP addr`   | PC <- addr                          |       |
| 0xC8   | `JZ addr`    | if Z, PC <- addr                    |       |
| 0xD0   | `JNZ addr`   | if !Z, PC <- addr                   |       |
| 0xD8   | `JC addr`    | if C, PC <- addr                    |       |
| 0xE0   | `INC addr`   | mem[addr] <- mem[addr] + 1          | Z, C  |
| 0xF0   | `HALT`       | stop the core                       |       |
| 0xFE   | `OUTI imm`   | GPIO <- imm                         |       |

For `SUBI`/`SUBM`, C is set when there is **no** borrow (A >= operand).

### Memory map

| Address | Read                    | Write                       |
|---------|-------------------------|-----------------------------|
| 0x00-1F | RAM                     | RAM                         |
| 0xFC    | GPIO output register    | GPIO output register (uio)  |
| 0xFD    | ui[7:0] input pins      | -                           |
| 0xFE    | last received UART byte | send byte over UART         |
| 0xFF    | bit0 = TX busy, bit1 = RX available | -               |

Reading `0xFE` clears the RX-available flag.  Writing `0xFE` while the
transmitter is busy is ignored - poll `0xFF` bit0 first.  RAM contents are
not initialised: store before you load.

## How to test

Release reset, then send a program over UART (`ui[0]`) at 115200 8N1,
e.g. `10 07 40 03 30 FC F0` (A = 7 + 3, GPIO = result, halt) prefixed with
`'L'`, length 7, and followed by `'R'`.  The result appears on `uio[7:0]`;
the blue LED lights when the CPU halts.

## External hardware

A USB-UART adapter at 115200 8N1 plus 8 LEDs (or a logic analyser) on
`uio[7:0]`, and 3 LEDs on `uo[1..3]`.
