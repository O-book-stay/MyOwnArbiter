`timescale 1ns/1ps
`include "puf_defines.v"

// ============================================================
// Tiny Tapeout top-level wrapper for the Arbiter PUF project.
//
//   ui[7:0] + uio[7:0] : parallel challenge bus
//       challenge = {ui_in, uio_in}  (ui[7]=bit15 ... uio[0]=bit0).
//       A bus value DIFFERENT from the previously measured one
//       starts the next measurement; pulse rst_n to re-measure
//       the same challenge.
//   uo[0]  : UART TX (115200 8N1, response = 4 hex chars)
//   uo[1]  : LED R  (measurement in progress)
//   uo[2]  : LED G  (race activity / sending)
//   uo[3]  : LED B  (waiting for a new challenge)
//
// The `ena` input gates the internal reset so the design stays in
// reset until the project is selected on the chip.
// ============================================================

module tt_um_obookstay_puf (
    input  wire [7:0] ui_in,     // Dedicated inputs
    output wire [7:0] uo_out,    // Dedicated outputs
    input  wire [7:0] uio_in,    // IOs: Input path
    output wire [7:0] uio_out,   // IOs: Output path
    output wire [7:0] uio_oe,    // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,       // enable - goes high when design is selected
    input  wire       clk,       // clock
    input  wire       rst_n      // not reset
`ifdef USE_POWER_PINS
    ,
    inout  wire       VPWR,
    inout  wire       VGND
`endif
);

    wire        uart_tx;
    wire [15:0] challenge_bus = {ui_in, uio_in};
    wire led_r, led_g, led_b;
    wire rst_int = rst_n & ena;

    puf_top u_puf_top (
        .clk     (clk),
        .rst_n   (rst_int),
        .uart_tx (uart_tx),
        .challenge_bus (challenge_bus),
        .led_r   (led_r),
        .led_g   (led_g),
        .led_b   (led_b)
`ifdef USE_POWER_PINS
        ,
        .VPWR    (VPWR),
        .VGND    (VGND)
`endif
    );

    assign uo_out[0] = uart_tx;
    assign uo_out[1] = led_r;
    assign uo_out[2] = led_g;
    assign uo_out[3] = led_b;
    assign uo_out[4] = 1'b0;
    assign uo_out[5] = 1'b0;
    assign uo_out[6] = 1'b0;
    assign uo_out[7] = 1'b0;

    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

endmodule
