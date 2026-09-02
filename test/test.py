# SPDX-FileCopyrightText: © 2026 O-book-stay
# SPDX-License-Identifier: Apache-2.0

# cocotb testbench for the Arbiter PUF (tt_um_obookstay_puf).
#
# Protocol under test (parallel challenge bus):
#   * challenge[15:0] = {ui_in, uio_in}; a bus value DIFFERENT from
#     the previously measured one starts the next measurement
#   * receive the 16-bit response as 4 hex chars on uo[0]
#     (UART 115200 8N1)
#   * two rounds (challenge A / challenge B) must both complete and
#     produce different responses.
#
# UART timing is done in clock cycles (BIT_CYCLES per bit, matching
# `BIT_PERIOD` in src/puf_defines.v) so the test is exact regardless
# of the simulated clock period. All wait loops are bounded so a
# failure fails fast.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

BIT_CYCLES = 416  # CLK_FREQ / BAUD_RATE = 48MHz / 115200 (see puf_defines.v)
HALF_BIT = 208    # BIT_CYCLES / 2 (even)
NBYTES = 4        # RESP_BITS / 4

HEX_CHARS = set("0123456789ABCDEFabcdef")

MAX_WAIT_CYCLES = 2_000_000  # per received byte


def _uart_bit(dut):
    """Return uo[0] (UART line) as a 0/1 int.

    Only bit 0 matters for the test; the upper bits (led_g/led_b etc,
    driven from the arbiter race) can legitimately be X/Z during a
    measurement, and ``int()`` on the whole 8-bit bus raises ValueError
    in cocotb 2.0 when any bit is unknown. Read just the LSB and treat
    an unknown bit as idle (1) so we never crash.
    """
    try:
        return int(dut.uo_out.value[0])
    except ValueError:
        return 1


async def recv_byte(dut):
    """Wait for the start bit on uo[0], then sample one 8N1 byte mid-bit."""
    for _ in range(MAX_WAIT_CYCLES):
        if _uart_bit(dut) == 0:
            break
        await ClockCycles(dut.clk, 1)
    else:
        raise AssertionError("timeout waiting for UART start bit")
    await ClockCycles(dut.clk, HALF_BIT)  # mid of start bit
    val = 0
    for k in range(8):
        await ClockCycles(dut.clk, BIT_CYCLES)
        if _uart_bit(dut):
            val |= 1 << k
    await ClockCycles(dut.clk, BIT_CYCLES)  # stop bit
    return val


async def recv_response(dut):
    out = []
    for _ in range(NBYTES):
        b = await recv_byte(dut)
        out.append(b)
        assert chr(b) in HEX_CHARS, f"byte {len(out)} 0x{b:02x} is not a hex char"
    return out


def drive_challenge(dut, value):
    """Put a 16-bit challenge on {ui_in, uio_in}."""
    dut.ui_in.value = (value >> 8) & 0xFF
    dut.uio_in.value = value & 0xFF


@cocotb.test(timeout_time=30000, timeout_unit="ms")
async def test_puf_roundtrip(dut):
    """Run two challenge/response rounds."""

    cocotb.start_soon(Clock(dut.clk, 20, units="ns").start())  # 50 MHz

    dut.ena.value = 1
    drive_challenge(dut, 0xA5C3)  # round-1 challenge before reset release
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)

    # 1. Round 1: first bus value after reset fires immediately
    dut._log.info("Round 1: challenge A = 0xA5C3")
    resp1 = await recv_response(dut)
    dut._log.info("Round 1 response: %s", "".join(chr(b) for b in resp1))

    # 2. Round 2: change the bus -> the controller detects the new
    #    value and starts the next measurement automatically
    dut._log.info("Round 2: challenge B = 0x3C5A")
    drive_challenge(dut, 0x3C5A)
    resp2 = await recv_response(dut)
    dut._log.info("Round 2 response: %s", "".join(chr(b) for b in resp2))

    # 3. Challenge-dependent responses must differ
    assert resp1 != resp2, "responses to different challenges must differ"

    dut._log.info("PASS: two challenge/response rounds completed")
