`timescale 1ns / 1ps
`default_nettype none

// ============================================================
// Self-checking UART smoke testbench (no cocotb dependency).
//
// Mirrors test/test.py: 8-hex-char challenge in, 8-hex-char
// response out, two rounds, responses must differ. Bit timing is
// cycle-exact (416 clocks/bit like BIT_PERIOD in puf_defines.v).
// Run with iverilog:
//   iverilog -g2012 -s tb_smoke -I../src tb_smoke.v \
//     ../src/puf_defines.v ../src/arb_mux.v ../src/arbiter_chain.v \
//     ../src/arbiter_cell.v ../src/puf_top.v \
//     ../src/puf_controller.v ../src/lfsr.v ../src/uart_rx.v \
//     ../src/uart_tx.v ../src/tt_um_obookstay_puf.v \
//     ../src/macro/arbchain.v && vvp a.out
// ============================================================

module tb_smoke;
  reg clk = 1'b0;
  always #10 clk = ~clk;  // 50 MHz (bit times are counted in cycles)

  reg rst_n = 1'b0;
  reg [7:0] ui_in = 8'hFF;  // UART RX idle high
  wire [7:0] uo_out, uio_out, uio_oe;

  tt_um_obookstay_puf dut (
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (8'h00),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (1'b1),
      .clk    (clk),
      .rst_n  (rst_n)
  );

  localparam integer BIT_NS  = 8320;  // 416 cycles x 20 ns
  localparam integer HALF_NS = 4160;
  localparam integer GAP_NS  = 1280;  // inter-byte idle gap

  task send_byte(input [7:0] d);
    integer b;
    begin
      ui_in[0] = 1'b0;  // start bit
      #(BIT_NS);
      for (b = 0; b < 8; b = b + 1) begin
        ui_in[0] = d[b];
        #(BIT_NS);
      end
      ui_in[0] = 1'b1;  // stop bit + gap
      #(BIT_NS + GAP_NS);
    end
  endtask

  task recv_byte(output [7:0] d);
    integer b, waited;
    begin
      d      = 8'h00;
      waited = 0;
      while (uo_out[0] !== 1'b0) begin
        #(1000);
        waited = waited + 1000;
        if (waited > 60_000_000) begin
          $display("FAIL: RX start-bit timeout");
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

  task wait_blue;  // led_b (uo[3]) high = waiting for a challenge
    integer waited;
    begin
      waited = 0;
      while (uo_out[3] !== 1'b1) begin
        #(1000);
        waited = waited + 1000;
        if (waited > 60_000_000) begin
          $display("FAIL: led_b wait timeout");
          $finish;
        end
      end
    end
  endtask

  function is_hex(input [7:0] c);
    is_hex = ((c >= "0" && c <= "9") || (c >= "A" && c <= "F") ||
              (c >= "a" && c <= "f"));
  endfunction

  reg [63:0] ch_a = 64'h3031323334353637;  // "01234567"
  reg [63:0] ch_b = 64'h3736353433323130;  // "76543210"
  reg [7:0]  r1 [0:7];
  reg [7:0]  r2 [0:7];
  reg [63:0] s1, s2;
  integer i, diff;

  initial begin
    $dumpfile("tb_smoke.fst");
    $dumpvars(0, tb_smoke);
  end

  initial begin
    #200_000_000;  // global watchdog
    $display("FAIL: global watchdog timeout");
    $finish;
  end

  initial begin
    #200;
    rst_n = 1'b1;
    #200;

    wait_blue;
    $display("TB: waiting for challenge (led_b=1)");

    // Round 1
    for (i = 0; i < 8; i = i + 1) send_byte(ch_a[63 - i*8 -: 8]);
    s1 = 64'h0;
    for (i = 0; i < 8; i = i + 1) begin
      recv_byte(r1[i]);
      if (!is_hex(r1[i])) begin
        $display("FAIL: round1 byte %0d = 0x%02x not hex", i, r1[i]);
        $finish;
      end
      s1 = {s1[55:0], r1[i]};
    end
    $display("TB: round1 response = %0s", s1);

    // Round 2
    wait_blue;
    for (i = 0; i < 8; i = i + 1) send_byte(ch_b[63 - i*8 -: 8]);
    s2 = 64'h0;
    for (i = 0; i < 8; i = i + 1) begin
      recv_byte(r2[i]);
      if (!is_hex(r2[i])) begin
        $display("FAIL: round2 byte %0d = 0x%02x not hex", i, r2[i]);
        $finish;
      end
      s2 = {s2[55:0], r2[i]};
    end
    $display("TB: round2 response = %0s", s2);

    diff = 0;
    for (i = 0; i < 8; i = i + 1)
      if (r1[i] !== r2[i]) diff = diff + 1;

    if (diff == 0) $display("FAIL: responses identical");
    else           $display("PASS: two rounds completed, responses differ in %0d/8 chars", diff);
    $finish;
  end
endmodule

`default_nettype wire
