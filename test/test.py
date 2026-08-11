# SPDX-FileCopyrightText: © 2026 O-book-stay
# SPDX-License-Identifier: Apache-2.0

# cocotb testbench for the Arbiter PUF (tt_um_obookstay_puf).
#
# The RTL contains no `initial` on purpose (the silicon power-up entropy
# bank must stay physically random), so the test seeds the bank through
# the hierarchy to keep the RTL simulation deterministic:
#   dut.u_puf_top.u_silicon_entropy.st.setimmediatevalue(...)
#
# Protocol under test (UART 115200 8N1, 48 MHz clock):
#   * send a 32-hex-char challenge on ui[0]
#   * receive the 128-bit response as 32 hex chars on uo[0]
#   * two rounds (challenge A / challenge B) must both complete.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, Timer

CLK_PERIOD_NS = 20.8333  # 48 MHz
BIT_NS = 1e9 / 115200    # UART bit period @ 115200 baud
NBYTES = 32              # RESP_BITS / 4

HEX_CHARS = set("0123456789ABCDEFabcdef")


async def send_byte(dut, data):
    """Transmit one 8N1 byte on ui[0] (LSB first)."""
    dut.ui_in[0].value = 0  # start bit
    await Timer(BIT_NS, units="ns")
    for k in range(8):
        dut.ui_in[0].value = (data >> k) & 1
        await Timer(BIT_NS, units="ns")
    dut.ui_in[0].value = 1  # stop bit
    await Timer(BIT_NS, units="ns")


async def send_challenge(dut, chars):
    for c in chars:
        await send_byte(dut, ord(c))


async def recv_byte(dut):
    """Wait for a falling edge on uo[0] and sample one 8N1 byte mid-bit."""
    await FallingEdge(dut.uo_out[0])
    await Timer(BIT_NS * 0.5, units="ns")  # mid of start bit
    val = 0
    for k in range(8):
        await Timer(BIT_NS, units="ns")
        if int(dut.uo_out[0].value):
            val |= 1 << k
    await Timer(BIT_NS, units="ns")  # stop bit
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
        if int(dut.uo_out[idx].value) == value:
            return
        await Timer(100, units="ns")


@cocotb.test(timeout_time=120, timeout_unit="s")
async def test_puf_roundtrip(dut):
    """Seed the silicon entropy bank, then run two challenge/response rounds."""

    # Seed the uninitialised power-up bank for a deterministic RTL sim.
    dut.u_puf_top.u_silicon_entropy.st.setimmediatevalue(
        int("0123456789ABCDEF0123456789ABCDEF", 16)
    )

    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, units="ns").start())

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
