# SPDX-FileCopyrightText: © 2026 O-book-stay
# SPDX-License-Identifier: Apache-2.0

# cocotb testbench for the Arbiter PUF (tt_um_obookstay_puf).
#
# The RTL contains no `initial` on purpose (the silicon power-up entropy
# bank must stay physically random), so the test seeds the bank through
# the hierarchy to keep the RTL simulation deterministic:
#   dut.user_project.u_puf_top.u_silicon_entropy.st.setimmediatevalue(...)
#
# Protocol under test (UART 115200 8N1):
#   * send a 32-hex-char challenge on ui[0]
#   * receive the 128-bit response as 32 hex chars on uo[0]
#   * two rounds (challenge A / challenge B) must both complete.
#
# UART timing is done in clock cycles (BIT_CYCLES per bit, matching
# `BIT_PERIOD` in src/puf_defines.v) instead of wall-clock timers, so the
# test is exact regardless of the simulated clock period.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

BIT_CYCLES = 416  # CLK_FREQ / BAUD_RATE = 48MHz / 115200 (see puf_defines.v)
HALF_BIT = 208    # BIT_CYCLES / 2 (even)
NBYTES = 32       # RESP_BITS / 4

HEX_CHARS = set("0123456789ABCDEFabcdef")

UART_RX_MASK = 0x01  # ui[0] is the UART RX pin; other ui bits stay high


def ui_value(bit0):
    """Build a ui_in vector with bit0 = bit0 and the other bits idle high."""
    return (0xFF & ~UART_RX_MASK) | (bit0 & UART_RX_MASK)


async def send_byte(dut, data):
    """Transmit one 8N1 byte on ui[0] (LSB first)."""
    dut.ui_in.value = ui_value(0)  # start bit
    await ClockCycles(dut.clk, BIT_CYCLES)
    for k in range(8):
        dut.ui_in.value = ui_value((data >> k) & 1)
        await ClockCycles(dut.clk, BIT_CYCLES)
    dut.ui_in.value = ui_value(1)  # stop bit
    await ClockCycles(dut.clk, BIT_CYCLES)


async def send_challenge(dut, chars):
    for c in chars:
        await send_byte(dut, ord(c))


async def recv_byte(dut):
    """Wait for the start bit on uo[0], then sample one 8N1 byte mid-bit."""
    while (int(dut.uo_out.value) & 1) == 1:
        await ClockCycles(dut.clk, 1)
    await ClockCycles(dut.clk, HALF_BIT)  # mid of start bit
    val = 0
    for k in range(8):
        await ClockCycles(dut.clk, BIT_CYCLES)
        if int(dut.uo_out.value) & 1:
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


def make_challenge():
    ch = []
    for i in range(NBYTES):
        if (i % 16) < 10:
            ch.append(chr(ord("0") + (i % 16)))
        else:
            ch.append(chr(ord("7") + (i % 16)))  # 'A'..'F'
    return ch


async def wait_led(dut, idx, value):
    """Wait until uo_out[idx] equals value."""
    while True:
        if (int(dut.uo_out.value) >> idx) & 1 == value:
            return
        await Timer(100, units="ns")


@cocotb.test(timeout_time=120000, timeout_unit="ms")
async def test_puf_roundtrip(dut):
    """Seed the silicon entropy bank, then run two challenge/response rounds."""

    # Seed the uninitialised power-up bank for a deterministic RTL sim.
    dut.user_project.u_puf_top.u_silicon_entropy.st.setimmediatevalue(
        int("0123456789ABCDEF0123456789ABCDEF", 16)
    )

    cocotb.start_soon(Clock(dut.clk, 20, units="ns").start())  # 50 MHz

    dut.ena.value = 1
    dut.ui_in.value = 0xFF  # UART RX idle high
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)

    # 1. The design must wait for a challenge (blue LED on uo[3])
    await wait_led(dut, 3, 1)
    dut._log.info("Waiting for challenge reached (led_b=1)")

    # 2. Round 1: challenge A
    ch_a = make_challenge()
    dut._log.info("Sending challenge A: %s", "".join(ch_a))
    await send_challenge(dut, ch_a)
    resp1 = await recv_response(dut)
    dut._log.info("Round 1 response: %s", "".join(chr(b) for b in resp1))

    # 3. Round 2: challenge B (completing round 2 implies the controller
    #    passed through S_DONE and returned to the challenge-wait state)
    await wait_led(dut, 3, 1)
    ch_b = list(reversed(ch_a))
    dut._log.info("Sending challenge B: %s", "".join(ch_b))
    await send_challenge(dut, ch_b)
    resp2 = await recv_response(dut)
    dut._log.info("Round 2 response: %s", "".join(chr(b) for b in resp2))

    # 4. Challenge-dependent responses must differ
    assert resp1 != resp2, "responses to different challenges must differ"

    dut._log.info("PASS: two challenge/response rounds completed")
