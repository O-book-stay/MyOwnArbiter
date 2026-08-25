`timescale 1ns / 1ps
`default_nettype none

// ============================================================
// Self-checking smoke testbench (no cocotb dependency).
//
// Protocol: the 16-bit parallel challenge bus {ui_in, uio_in}
// drives one measurement per DISTINCT bus value; the 16-bit
// response goes out as 4 hex chars on uo[0] (UART 115200 8N1).
// Two rounds with different challenges must both complete and
// produce different responses.  UART bit timing is cycle-exact
// (416 clocks/bit like BIT_PERIOD in puf_defines.v).
//
// Run with iverilog:
//   iverilog -g2012 -s tb_smoke -I../src tb_smoke.v \
//     ../src/puf_defines.v ../src/arb_mux.v ../src/arbiter_chain.v \
//     ../src/arbiter_cell.v ../src/puf_top.v \
//     ../src/puf_controller.v ../src/lfsr.v ../src/uart_tx.v \
//     ../src/tt_um_obookstay_puf.v \
//     ../src/macro/arbchain.v && vvp a.out
// ============================================================

module tb_smoke;
  reg clk = 1'b0;
  always #10 clk = ~clk;  // 50 MHz (bit times are counted in cycles)

  reg rst_n = 1'b0;
  reg [15:0] challenge = 16'h0000;
  wire [7:0] ui_in  = challenge[15:8];
  wire [7:0] uio_in = challenge[7:0];
  wire [7:0] uo_out, uio_out, uio_oe;

  tt_um_obookstay_puf dut (
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (uio_in),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (1'b1),
      .clk    (clk),
      .rst_n  (rst_n)
  );

  localparam integer BIT_NS  = 8320;  // 416 cycles x 20 ns
  localparam integer HALF_NS = 4160;
  localparam integer GAP_NS  = 1280;  // inter-byte idle gap
  localparam integer NBYTES  = 4;     // RESP_BITS / 4

  task recv_byte(output [7:0] d);
    integer b, waited;
    begin
      d      = 8'h00;
      waited = 0;
      while (uo_out[0] !== 1'b0) begin
        #(1000);
        waited = waited + 1000;
        if (waited > 60_000_000) begin
          $display("FAIL: TX start-bit timeout");
          $finish;
        end
      end
      #(HALF_NS);  // middle of the start bit
      for (b = 0; b < 8; b = b + 1) begin
        #(BIT_NS);
        d[b] = uo_out[0];
      end
      #(BIT_NS);  // stop bit
    end
  endtask

  function is_hex(input [7:0] c);
    is_hex = ((c >= "0" && c <= "9") || (c >= "A" && c <= "F") ||
              (c >= "a" && c <= "f"));
  endfunction

  // One measurement round: wait for the 4-char response.
  task recv_response(output [31:0] resp);
    reg [7:0] r;
    integer i;
    begin
      resp = 32'h0;
      for (i = 0; i < NBYTES; i = i + 1) begin
        recv_byte(r);
        if (!is_hex(r)) begin
          $display("FAIL: response byte %0d = 0x%02x not hex", i, r);
          $finish;
        end
        resp = {resp[23:0], r};
      end
    end
  endtask

  reg [31:0] s1, s2;
  integer diff;

  initial begin
    $dumpfile("tb_smoke.fst");
    $dumpvars(0, tb_smoke);
  end

  initial begin
    #50_000_000;  // global watchdog
    $display("FAIL: global watchdog timeout");
    $finish;
  end

  initial begin
    // Round 1: drive challenge A before releasing reset; the first
    // round after reset fires on any bus value.
    challenge = 16'hA5C3;
    #200;
    rst_n = 1'b1;
    recv_response(s1);
    $display("TB: round1 response = %08x (challenge A5C3)", s1);

    // Round 2: change the bus -> the controller detects the new
    // value and starts the next measurement automatically.
    challenge = 16'h3C5A;
    recv_response(s2);
    $display("TB: round2 response = %08x (challenge 3C5A)", s2);

    if (s1 === s2) $display("FAIL: responses identical");
    else           $display("PASS: two rounds completed, responses differ");
    $finish;
  end
endmodule

`default_nettype wire
