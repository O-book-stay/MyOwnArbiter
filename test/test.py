# SPDX-FileCopyrightText: © 2026 O-book-stay
# SPDX-License-Identifier: Apache-2.0

# cocotb testbench for the 8-bit multicycle CPU (tt_um_obookstay_cpu).
#
# The design boots over UART (115200 8N1 on ui[0]/uo[0]):
#   'L' + len + len program bytes  -> program image into RAM at 0x00
#   'R'                            -> run from PC = 0
# Programs talk through memory-mapped IO:
#   0xFC GPIO output (uio), 0xFE UART data, 0xFF status
#   (bit0 = TX busy, bit1 = RX byte available).
# LEDs on uo[3:1] = {B, G, R}: R boot/loading, G running, B halted.
#
# UART timing is done in clock cycles (BIT_CYCLES per bit, matching
# `BIT_PERIOD` in src/cpu_defines.v) instead of wall-clock timers, so the
# test is exact regardless of the simulated clock period. A short idle gap
# is held between bytes so the design's RX synchroniser never misses a
# start bit. All wait loops are bounded so a failure fails fast.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

BIT_CYCLES = 416  # CLK_FREQ / BAUD_RATE = 48MHz / 115200 (see cpu_defines.v)
HALF_BIT = 208    # BIT_CYCLES / 2 (even)
INTER_BYTE_GAP = 64  # idle cycles between bytes

MAX_WAIT_CYCLES = 2_000_000  # per LED / GPIO / byte wait

# ISA (keep in sync with src/cpu_defines.v)
OP_LDI = 0x10
OP_LDD = 0x20
OP_STD = 0x30
OP_ADDI = 0x40
OP_ADDM = 0x50
OP_SUBI = 0x60
OP_ANDI = 0x80
OP_MOV_BA = 0xB0
OP_MOV_AB = 0xB8
OP_JMP = 0xC0
OP_JZ = 0xC8
OP_JNZ = 0xD0
OP_INC = 0xE0
OP_HALT = 0xF0
OP_OUTI = 0xFE

ADDR_GPIO = 0xFC
ADDR_UART_DATA = 0xFE
ADDR_UART_STAT = 0xFF

BOOT_LOAD = 0x4C  # 'L'
BOOT_RUN = 0x52   # 'R'

# LED triples on uo[3:1] = {B, G, R}
LED_BOOT = 0b001
LED_RUN = 0b010
LED_HALT = 0b100


def ui_value(bit0):
    """Build a ui_in vector with bit0 = bit0 and the other bits idle high."""
    return (0xFF & ~0x01) | (bit0 & 0x01)


async def send_byte(dut, data):
    """Transmit one 8N1 byte on ui[0] (LSB first) plus an idle gap."""
    dut.ui_in.value = ui_value(0)  # start bit
    await ClockCycles(dut.clk, BIT_CYCLES)
    for k in range(8):
        dut.ui_in.value = ui_value((data >> k) & 1)
        await ClockCycles(dut.clk, BIT_CYCLES)
    dut.ui_in.value = ui_value(1)  # stop bit + gap
    await ClockCycles(dut.clk, BIT_CYCLES + INTER_BYTE_GAP)


async def recv_byte(dut):
    """Wait for the start bit on uo[0], then sample one 8N1 byte mid-bit."""
    for _ in range(MAX_WAIT_CYCLES):
        if (int(dut.uo_out.value) & 1) == 0:
            break
        await ClockCycles(dut.clk, 1)
    else:
        raise AssertionError("TX start-bit timeout")

    await ClockCycles(dut.clk, HALF_BIT)  # centre of the start bit
    data = 0
    for k in range(8):
        await ClockCycles(dut.clk, BIT_CYCLES)
        data |= (int(dut.uo_out.value) & 1) << k
    await ClockCycles(dut.clk, BIT_CYCLES)  # stop bit
    return data


async def boot_load(dut, prog):
    """Send the boot sequence: 'L', length, image, 'R'."""
    await send_byte(dut, BOOT_LOAD)
    await send_byte(dut, len(prog))
    for b in prog:
        await send_byte(dut, b)
    await send_byte(dut, BOOT_RUN)


async def wait_led(dut, rgb):
    """Poll until uo[3:1] equals rgb; bounded."""
    for _ in range(MAX_WAIT_CYCLES):
        if ((int(dut.uo_out.value) >> 1) & 0b111) == rgb:
            return True
        await ClockCycles(dut.clk, 1)
    return False


async def wait_gpio(dut, expected):
    """Poll until uio_out equals expected; bounded."""
    for _ in range(MAX_WAIT_CYCLES):
        if (int(dut.uio_out.value) & 0xFF) == expected:
            return True
        await ClockCycles(dut.clk, 1)
    return False


async def reset(dut):
    """Hold the design in reset, then release it with the clock running."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    dut.ui_in.value = 0xFF  # UART RX idle high
    dut.uio_in.value = 0x00
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)


@cocotb.test()
async def test_gpio_program(dut):
    """Boot state, then LDI/ADDI/STD/HALT: 7+3 must reach the GPIO output."""
    await reset(dut)

    assert await wait_led(dut, LED_BOOT), "boot LED (R) not observed"
    assert (int(dut.uio_oe.value) & 0xFF) == 0xFF, "uio_oe must drive all pins"
    assert (int(dut.uio_out.value) & 0xFF) == 0x00, "GPIO must be 0 after reset"

    prog = [OP_LDI, 0x07, OP_ADDI, 0x03, OP_STD, ADDR_GPIO, OP_HALT]
    await boot_load(dut, prog)

    assert await wait_gpio(dut, 0x0A), "GPIO != 0x0A after LDI 7 / ADDI 3"
    assert await wait_led(dut, LED_HALT), "CPU did not halt"


@cocotb.test()
async def test_uart_tx_program(dut):
    """TX 'A', poll TX-busy via MMIO, TX 'B': both bytes must come out."""
    await reset(dut)

    prog = [
        OP_LDI, 0x41,             # 'A'
        OP_STD, ADDR_UART_DATA,   # send it
        OP_LDD, ADDR_UART_STAT,   # poll status
        OP_ANDI, 0x01,            # isolate TX busy
        OP_JNZ, 0x04,             # still busy -> poll again
        OP_LDI, 0x42,             # 'B'
        OP_STD, ADDR_UART_DATA,   # send it
        OP_HALT,
    ]
    await boot_load(dut, prog)

    rx1 = await recv_byte(dut)
    rx2 = await recv_byte(dut)
    assert rx1 == 0x41, f"first UART byte = 0x{rx1:02x}, expected 0x41"
    assert rx2 == 0x42, f"second UART byte = 0x{rx2:02x}, expected 0x42"

    assert await wait_led(dut, LED_HALT), "CPU did not halt after TX"


@cocotb.test()
async def test_loop_program(dut):
    """Counter loop with ADDM/SUBI/JMP/JZ: sum 3+2+1 = 6 on the GPIO."""
    await reset(dut)

    prog = [
        OP_LDI, 0x03,       # counter = 3
        OP_STD, 0x20,
        OP_LDI, 0x00,       # sum = 0
        OP_STD, 0x21,
        OP_LDD, 0x20,       # loop: A = counter
        OP_JZ, 0x1A,        # done?
        OP_LDD, 0x21,       # A = sum
        OP_ADDM, 0x20,      # A += counter
        OP_STD, 0x21,       # sum = A
        OP_LDD, 0x20,       # A = counter
        OP_SUBI, 0x01,      # counter-1
        OP_STD, 0x20,
        OP_JMP, 0x08,
        OP_LDD, 0x21,       # done: A = sum
        OP_STD, ADDR_GPIO,  # GPIO = sum
        OP_HALT,
    ]
    await boot_load(dut, prog)

    assert await wait_gpio(dut, 0x06), "GPIO != 0x06 (sum 3+2+1)"
    assert await wait_led(dut, LED_HALT), "CPU did not halt"
