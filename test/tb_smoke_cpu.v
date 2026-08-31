`timescale 1ns / 1ps
`default_nettype none
`include "cpu_defines.v"

// ============================================================================
// Self-checking smoke testbench for the 8-bit multicycle CPU
// (tt_um_obookstay_cpu).  No cocotb dependency -- plain iverilog.
//
// Coverage:
//   * boot protocol ('L' + len + image, 'R') and LED state machine
//   * program 1: LDI/ADDI/STD/HALT            -> GPIO == 0x0A
//   * program 2: UART TX + busy polling loop  -> receives 'A', 'B'
//   * program 3: counter loop w/ ADDM/SUBI/JMP/JZ -> GPIO == 0x06
//   * program 4: MOV*, INC, SUBM, OUTI        -> GPIO == 0x04
//
// Run with iverilog:
//   iverilog -g2012 -s tb_smoke_cpu -I../src tb_smoke_cpu.v \
//     ../src/cpu_defines.v ../src/cpu_core.v ../src/cpu_top.v \
//     ../src/uart_rx.v ../src/uart_tx.v ../src/tt_um_obookstay_cpu.v \
//     && vvp a.out
// ============================================================================

module tb_smoke_cpu;

  reg clk = 1'b0;
  always #10 clk = ~clk;  // 50 MHz; UART timing is cycle-based anyway

  reg       rst_n = 1'b0;
  reg [7:0] ui_in = 8'hFF;   // UART RX idle high
  wire [7:0] uo_out, uio_out, uio_oe;

  tt_um_obookstay_cpu dut (
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (8'h00),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (1'b1),
      .clk    (clk),
      .rst_n  (rst_n)
  );

  localparam integer BIT_NS     = 20 * `BIT_PERIOD;  // 416 cycles * 20 ns
  localparam integer HALF_NS    = BIT_NS / 2;
  localparam integer GAP_NS     = 20 * 64;           // inter-byte idle gap
  localparam integer POLL_LIMIT = 500_000;           // clock cycles per poll

  // LED triple on uo_out[3:1] = {B, G, R}
  localparam [2:0] LED_BOOT = 3'b001;   // R on
  localparam [2:0] LED_RUN  = 3'b010;   // G on
  localparam [2:0] LED_HALT = 3'b100;   // B on

  integer errors = 0;
  reg task_ok;                           // last wait_* task succeeded

  // ------------------------------------------------------------------
  // UART helpers (8-N-1, LSB first, like the real link)
  // ------------------------------------------------------------------
  task send_byte(input [7:0] d);
    integer b;
    begin
      ui_in[0] = 1'b0;  // start bit
      #(BIT_NS);
      for (b = 0; b < 8; b = b + 1) begin
        ui_in[0] = d[b];
        #(BIT_NS);
      end
      ui_in[0] = 1'b1;  // stop bit + idle gap
      #(BIT_NS + GAP_NS);
    end
  endtask

  task recv_byte(output [7:0] d);
    integer b, waited;
    begin
      d        = 8'h00;
      waited   = 0;
      task_ok  = 1'b1;
      while (uo_out[0] !== 1'b0) begin
        @(posedge clk);
        waited = waited + 1;
        if (waited > POLL_LIMIT) begin
          $display("FAIL: TX start-bit timeout");
          errors  = errors + 1;
          task_ok = 1'b0;
          disable recv_byte;
        end
      end
      #(HALF_NS);  // centre of the start bit
      for (b = 0; b < 8; b = b + 1) begin
        #(BIT_NS);
        d[b] = uo_out[0];
      end
      #(BIT_NS);   // stop bit
    end
  endtask

  // ------------------------------------------------------------------
  // Boot helpers
  // ------------------------------------------------------------------
  reg [7:0] prog_image [0:`RAM_DEPTH-1];

  task boot_load(input [7:0] len);
    integer i;
    begin
      send_byte(`BOOT_LOAD);
      send_byte(len);
      for (i = 0; i < len; i = i + 1)
        send_byte(prog_image[i]);
      send_byte(`BOOT_RUN);
    end
  endtask

  // Poll until the LED triple matches.
  task wait_led(input [2:0] rgb);
    integer waited;
    begin
      waited  = 0;
      task_ok = 1'b1;
      while (uo_out[3:1] !== rgb) begin
        @(posedge clk);
        waited = waited + 1;
        if (waited > POLL_LIMIT) begin
          $display("FAIL: LED wait timeout (want %b, got %b)", rgb, uo_out[3:1]);
          errors  = errors + 1;
          task_ok = 1'b0;
          disable wait_led;
        end
      end
    end
  endtask

  // Poll until uio_out equals the expected value.
  task check_gpio(input [7:0] expected);
    integer waited;
    begin
      waited  = 0;
      task_ok = 1'b1;
      while (uio_out !== expected) begin
        @(posedge clk);
        waited = waited + 1;
        if (waited > POLL_LIMIT) begin
          $display("FAIL: GPIO wait timeout (want 0x%02x, got 0x%02x)",
                   expected, uio_out);
          errors  = errors + 1;
          task_ok = 1'b0;
          disable check_gpio;
        end
      end
    end
  endtask

  // ------------------------------------------------------------------
  // Watchdogs
  // ------------------------------------------------------------------
  initial begin
    $dumpfile("tb_smoke_cpu.fst");
    $dumpvars(0, tb_smoke_cpu);
  end

  initial begin
    #500_000_000;  // 500 ms global watchdog
    $display("FAIL: global watchdog timeout");
    $finish;
  end

  // ------------------------------------------------------------------
  // Main sequence.  Each program is written into prog_image immediately
  // before it is booted.
  // ------------------------------------------------------------------
  reg [7:0] rx1, rx2;
  integer i;

  initial begin
    #200;
    rst_n = 1'b1;

    // Boot state: LED R on, GPIO idle 0.
    wait_led(LED_BOOT);
    if (task_ok) $display("TB: boot state OK (LED R on)");
    if (uio_out !== 8'h00) begin
      $display("FAIL: GPIO not 0 after reset (0x%02x)", uio_out);
      errors = errors + 1;
    end

    // ---- Program 1: LDI 7; ADDI 3; STD GPIO; HALT (7 bytes) --------
    $display("TB: program 1 (LDI/ADDI/STD/HALT)");
    prog_image[0] = `OP_LDI;  prog_image[1] = 8'h07;
    prog_image[2] = `OP_ADDI; prog_image[3] = 8'h03;
    prog_image[4] = `OP_STD;  prog_image[5] = `ADDR_GPIO;
    prog_image[6] = `OP_HALT;
    boot_load(8'd7);
    // NOTE: this program finishes in <1 us -- faster than the 'R' stop bit,
    // so the RUN LED phase is not observable here.  Check the outcome only.
    check_gpio(8'h0A);      if (task_ok) $display("TB: prog1 GPIO = 0x0A OK");
    wait_led(LED_HALT);     if (task_ok) $display("TB: prog1 halted");

    // ---- Program 2: TX 'A'; poll TX-busy; TX 'B'; HALT (15 bytes) --
    $display("TB: program 2 (UART TX poll)");
    prog_image[0]  = `OP_LDI;  prog_image[1]  = 8'h41;         // 'A'
    prog_image[2]  = `OP_STD;  prog_image[3]  = `ADDR_UART_DATA;
    prog_image[4]  = `OP_LDD;  prog_image[5]  = `ADDR_UART_STAT;
    prog_image[6]  = `OP_ANDI; prog_image[7]  = 8'h01;         // tx_busy
    prog_image[8]  = `OP_JNZ;  prog_image[9]  = 8'h04;         // poll again
    prog_image[10] = `OP_LDI;  prog_image[11] = 8'h42;         // 'B'
    prog_image[12] = `OP_STD;  prog_image[13] = `ADDR_UART_DATA;
    prog_image[14] = `OP_HALT;
    boot_load(8'd15);
    wait_led(LED_RUN);      // the TX poll loop is long enough to observe
    recv_byte(rx1);
    recv_byte(rx2);
    if (rx1 !== 8'h41 || rx2 !== 8'h42) begin
      $display("FAIL: UART TX got 0x%02x 0x%02x, expected 0x41 0x42", rx1, rx2);
      errors = errors + 1;
    end else begin
      $display("TB: UART TX received 'A','B' OK");
    end
    wait_led(LED_HALT);     if (task_ok) $display("TB: prog2 halted");

    // ---- Program 3: sum 3+2+1 = 6 into GPIO (31 bytes) -------------
    $display("TB: program 3 (loop sum)");
    prog_image[0]  = `OP_LDI;  prog_image[1]  = 8'h03;   // counter = 3
    prog_image[2]  = `OP_STD;  prog_image[3]  = 8'h20;
    prog_image[4]  = `OP_LDI;  prog_image[5]  = 8'h00;   // sum = 0
    prog_image[6]  = `OP_STD;  prog_image[7]  = 8'h21;
    prog_image[8]  = `OP_LDD;  prog_image[9]  = 8'h20;   // loop: A = counter
    prog_image[10] = `OP_JZ;   prog_image[11] = 8'h1A;   // done?
    prog_image[12] = `OP_LDD;  prog_image[13] = 8'h21;   // A = sum
    prog_image[14] = `OP_ADDM; prog_image[15] = 8'h20;   // A += counter
    prog_image[16] = `OP_STD;  prog_image[17] = 8'h21;   // sum = A
    prog_image[18] = `OP_LDD;  prog_image[19] = 8'h20;   // A = counter
    prog_image[20] = `OP_SUBI; prog_image[21] = 8'h01;   // counter-1
    prog_image[22] = `OP_STD;  prog_image[23] = 8'h20;
    prog_image[24] = `OP_JMP;  prog_image[25] = 8'h08;
    prog_image[26] = `OP_LDD;  prog_image[27] = 8'h21;      // A = sum
    prog_image[28] = `OP_STD;  prog_image[29] = `ADDR_GPIO; // GPIO = sum
    prog_image[30] = `OP_HALT;
    boot_load(8'd31);
    wait_led(LED_RUN);      // slow enough to catch the RUN phase
    check_gpio(8'h06);      if (task_ok) $display("TB: prog3 GPIO = 0x06 OK");
    wait_led(LED_HALT);     if (task_ok) $display("TB: prog3 halted");

    // ---- Program 4: MOV*, INC, SUBM, OUTI (15 bytes) ---------------
    $display("TB: program 4 (MOV/INC/SUBM/OUTI)");
    prog_image[0]  = `OP_LDI;    prog_image[1]  = 8'h05;   // A = 5
    prog_image[2]  = `OP_MOV_BA;                          // B = 5
    prog_image[3]  = `OP_LDI;    prog_image[4]  = 8'h00;
    prog_image[5]  = `OP_STD;    prog_image[6]  = 8'h20;   // mem[0x20] = 0
    prog_image[7]  = `OP_INC;    prog_image[8]  = 8'h20;   // mem[0x20] = 1
    prog_image[9]  = `OP_MOV_AB;                          // A = B = 5
    prog_image[10] = `OP_SUBM;   prog_image[11] = 8'h20;   // A = 5 - 1 = 4
    prog_image[12] = `OP_OUTI;   prog_image[13] = 8'h04;   // GPIO = 4
    prog_image[14] = `OP_HALT;
    boot_load(8'd15);
    // finishes quickly; check the outcome only
    check_gpio(8'h04);      if (task_ok) $display("TB: prog4 GPIO = 0x04 OK");
    wait_led(LED_HALT);     if (task_ok) $display("TB: prog4 halted");

    // ---- Summary ---------------------------------------------------
    if (errors == 0)
      $display("PASS: all smoke tests passed");
    else
      $display("FAIL: %0d error(s)", errors);
    $finish;
  end

endmodule

`default_nettype wire



