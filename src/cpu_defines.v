// ============================================================================
// cpu_defines.v -- shared definitions for the 8-bit multicycle CPU
// (tt_um_obookstay_cpu).  Included by the RTL and by the testbenches so the
// ISA encoding, MMIO map and UART timing stay in sync everywhere.
// ============================================================================

`ifndef CPU_DEFINES_V
`define CPU_DEFINES_V

// ---------------------------------------------------------------------------
// Clock / UART timing
// ---------------------------------------------------------------------------
`define CLK_FREQ    48000000
`define BAUD_RATE   115200
`define BIT_PERIOD  (`CLK_FREQ / `BAUD_RATE)   // 416 cycles per UART bit

// ---------------------------------------------------------------------------
// RAM geometry (program + data, loaded over UART at boot)
// ---------------------------------------------------------------------------
`define RAM_DEPTH   64
`define RAM_AW      6                          // address bits (0x00-0x3F)

// ---------------------------------------------------------------------------
// Memory-mapped IO (addresses 0xFC-0xFF)
// ---------------------------------------------------------------------------
`define ADDR_GPIO       8'hFC   // W/R: GPIO output register (uio[7:0])
`define ADDR_PINS       8'hFD   // R  : dedicated input pins ui[7:0]
`define ADDR_UART_DATA  8'hFE   // W: send byte over UART; R: last RX byte
                                //      (read clears the "available" flag)
`define ADDR_UART_STAT  8'hFF   // R: bit0 = TX busy, bit1 = RX byte available

// ---------------------------------------------------------------------------
// Instruction set (8-bit opcodes; "imm"/"addr" is a second byte)
//   0x00 NOP
//   0x10 LDI  imm     A  <- imm        (Z)
//   0x20 LDD  addr    A  <- mem[addr]  (Z)
//   0x30 STD  addr    mem[addr] <- A
//   0x40 ADDI imm     A  <- A + imm        (Z, C = carry)
//   0x50 ADDM addr    A  <- A + mem[addr]  (Z, C = carry)
//   0x60 SUBI imm     A  <- A - imm        (Z, C = no-borrow)
//   0x70 SUBM addr    A  <- A - mem[addr]  (Z, C = no-borrow)
//   0x80 ANDI imm     A  <- A & imm        (Z, C = 0)
//   0x90 ORI  imm     A  <- A | imm        (Z, C = 0)
//   0xA0 XORI imm     A  <- A ^ imm        (Z, C = 0)
//   0xB0 MOV B,A      B  <- A
//   0xB8 MOV A,B      A  <- B
//   0xC0 JMP addr     PC <- addr
//   0xC8 JZ  addr     if Z, PC <- addr
//   0xD0 JNZ addr     if !Z, PC <- addr
//   0xD8 JC  addr     if C, PC <- addr
//   0xE0 INC  addr    mem[addr] <- mem[addr] + 1  (Z, C = carry)
//   0xF0 HALT         stop the core
//   0xFE OUTI imm     GPIO <- imm  (shortcut for LDI+STD 0xFC)
// ---------------------------------------------------------------------------
`define OP_NOP     8'h00
`define OP_LDI     8'h10
`define OP_LDD     8'h20
`define OP_STD     8'h30
`define OP_ADDI    8'h40
`define OP_ADDM    8'h50
`define OP_SUBI    8'h60
`define OP_SUBM    8'h70
`define OP_ANDI    8'h80
`define OP_ORI     8'h90
`define OP_XORI    8'hA0
`define OP_MOV_BA  8'hB0
`define OP_MOV_AB  8'hB8
`define OP_JMP     8'hC0
`define OP_JZ      8'hC8
`define OP_JNZ     8'hD0
`define OP_JC      8'hD8
`define OP_INC     8'hE0
`define OP_HALT    8'hF0
`define OP_OUTI    8'hFE

// ---------------------------------------------------------------------------
// Boot protocol (UART 115200 8N1 on ui[0], host -> chip)
//   'L' (0x4C) : start loading, then 1 byte length N, then N program bytes
//   'R' (0x52) : reset PC to 0 and run
// Both commands are only accepted while the core is halted (after reset or
// after HALT).  Programs must fit in `RAM_DEPTH bytes at 0x00.
// ---------------------------------------------------------------------------
`define BOOT_LOAD  8'h4C
`define BOOT_RUN   8'h52

`endif  // CPU_DEFINES_V
