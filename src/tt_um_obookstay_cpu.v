`timescale 1ns/1ps

// ============================================================================
// Tiny Tapeout top-level wrapper for the 8-bit multicycle CPU project.
//
//   ui[0]  : UART RX (115200 8N1, boot loader / program input)
//   uo[0]  : UART TX (115200 8N1, program output)
//   uo[1]  : LED R  (boot / loading)
//   uo[2]  : LED G  (running)
//   uo[3]  : LED B  (halted)
//   uio    : CPU GPIO output register (memory-mapped at 0xFC)
//
// The `ena` input gates the internal reset so the design stays in
// reset until the project is selected on the chip.
// ============================================================================

module tt_um_obookstay_cpu (
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
    input  wire       VPWR,
    input  wire       VGND
`endif
);

    wire led_r, led_g, led_b;
    wire rst_int = rst_n & ena;

    cpu_top u_cpu (
        .clk         (clk),
        .rst_n       (rst_int),
        .uart_rx_pin (ui_in[0]),
        .uart_tx_pin (uo_out[0]),
        .led_r       (led_r),
        .led_g       (led_g),
        .led_b       (led_b),
        .ui_pins     (ui_in),
        .gpio_out    (uio_out)
    );

    assign uo_out[1] = led_r;
    assign uo_out[2] = led_g;
    assign uo_out[3] = led_b;
    assign uo_out[7:4] = 4'b0000;

    // uio is a pure output (GPIO register); inputs unused.
    assign uio_oe = 8'hFF;

endmodule
