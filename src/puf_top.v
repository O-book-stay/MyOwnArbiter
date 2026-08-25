/* verilator lint_off TIMESCALEMOD */
/* verilator lint_off WIDTHEXPAND */
/* verilator lint_off WIDTHTRUNC */
`timescale 1ns/1ps
`include "puf_defines.v"

module puf_top (
    input  wire     clk,
    input  wire     rst_n,
    output wire     uart_tx,
    input  wire [`RESP_BITS-1:0] challenge_bus,
    output wire     led_r,
    output wire     led_g,
    output wire     led_b
`ifdef USE_POWER_PINS
    ,
    input  wire     VPWR,
    input  wire     VGND
`endif
);

    // ============================================================
    // Internal wires
    // ============================================================
    // Arbiter chain + latch (keep nets visible so the optimizer never
    // considers the chain/arbiter dangling)
    (* keep = "true" *) wire launch;
    (* keep = "true" *) wire arb_rst_n;
    (* keep = "true" *) wire arb_q;

    // LFSR (challenge / keystream)
    wire                      lfsr_load;
    wire                      lfsr_en;
    wire                      lfsr_inject;
    wire [`ARB_STAGES-1:0]    lfsr_seed;
    wire [`ARB_STAGES-1:0]    lfsr_state;
    wire [`ARB_STAGES-1:0]    lfsr_xmask;

    // UART TX
    wire                      uart_tx_start;
    wire [7:0]                uart_tx_data;
    wire                      uart_tx_busy;
    wire                      uart_tx_done;

    // LED / race status
    wire                      led_g_ctrl;
    wire                      race_active;

    // ============================================================
    // 1. Arbiter switch chain (the strong-PUF core)
    //
    // On silicon this is the symmetric hard macro `arbchain`
    // (src/macro) whose two delay lines are laid out mirror
    // symmetric about the macro centreline, so the race outcome is
    // dominated by random process variation rather than systematic
    // routing skew.  `arbchain` is a black box in synthesis (its
    // `.vh` header is provided via MACROS in src/config.json); the
    // behavioural model (arbchain.v -> arbiter_chain + arbiter_cell)
    // is used for RTL simulation only.
    // ============================================================
    arbchain u_chain (
        .q         (arb_q),
        .launch    (launch),
        .arb_rst_n (arb_rst_n),
        .ch        (lfsr_state)
`ifdef USE_POWER_PINS
        ,
        .VPWR      (VPWR),
        .VGND      (VGND)
`endif
    );

    // ============================================================
    // 2. LFSR (challenge derivation + keystream)
    // ============================================================
    lfsr #(
        .W (`ARB_STAGES)
    ) u_lfsr (
        .clk         (clk),
        .rst_n       (rst_n),
        .load        (lfsr_load),
        .en          (lfsr_en),
        .inject_bit  (lfsr_inject),
        .xmask       (lfsr_xmask),
        .seed        (lfsr_seed),
        .state       (lfsr_state)
    );

    // ============================================================
    // 3. UART TX (response output)
    // ============================================================
    uart_tx u_uart_tx (
        .clk      (clk),
        .rst_n    (rst_n),
        .tx_start (uart_tx_start),
        .data_in  (uart_tx_data),
        .tx_pin   (uart_tx),
        .tx_busy  (uart_tx_busy),
        .tx_done  (uart_tx_done)
    );

    // ============================================================
    // 4. PUF controller (FSM)
    // ============================================================
    puf_controller u_controller (
        .clk          (clk),
        .rst_n        (rst_n),
        .launch       (launch),
        .arb_rst_n    (arb_rst_n),
        .arb_q        (arb_q),
        .lfsr_load    (lfsr_load),
        .lfsr_en      (lfsr_en),
        .lfsr_inject  (lfsr_inject),
        .lfsr_seed    (lfsr_seed),
        .lfsr_state   (lfsr_state),
        .lfsr_xmask   (lfsr_xmask),
        .uart_start   (uart_tx_start),
        .uart_data    (uart_tx_data),
        .uart_busy    (uart_tx_busy),
        .uart_done    (uart_tx_done),
        .challenge_bus(challenge_bus),
        .led_r        (led_r),
        .led_g        (led_g_ctrl),
        .led_b        (led_b),
        .race_active  (race_active)
    );

    // Mirror the arbiter output onto the green LED while a race is in
    // flight ("race activity" indicator). This also keeps a direct
    // combinational path from arb_q to a primary output.
    assign led_g = race_active ? arb_q : led_g_ctrl;

endmodule
