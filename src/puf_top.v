`timescale 1ns/1ps
`include "puf_defines.v"

module puf_top (
    input  wire     clk,
    input  wire     rst_n,
    output wire     uart_tx,
    input  wire     uart_rx,
    output wire     led_r,
    output wire     led_g,
    output wire     led_b
);

    // ============================================================
    // Internal wires
    // ============================================================
    (* keep = "true" *) wire [`RO_COUNT-1:0] ro_pulses;
    wire [4:0]                mux_sel_a;
    wire [4:0]                mux_sel_b;
    wire                      mux_a_out;
    wire                      mux_b_out;
    wire                      ro_enable;
    wire                      cnt_rst_n;
    reg  [`CNT_WIDTH-1:0]     cnt_a;
    reg  [`CNT_WIDTH-1:0]     cnt_b;

    // Arbiter chain + latch (keep nets visible so the optimizer never
    // considers the chain/arbiter dangling)
    (* keep = "true" *) wire launch;
    (* keep = "true" *) wire arb_rst_n;
    (* keep = "true" *) wire arb_q;
    (* keep = "true" *) wire top_out;
    (* keep = "true" *) wire bot_out;

    // Silicon power-up entropy bank (hybrid anchor)
    wire [`SILICON_W-1:0]     silicon_bits;

    // LFSR (challenge / keystream)
    wire                      lfsr_load;
    wire                      lfsr_en;
    wire                      lfsr_inject;
    wire [`ARB_STAGES-1:0]    lfsr_seed;
    wire [`ARB_STAGES-1:0]    lfsr_state;
    wire [`ARB_STAGES-1:0]    lfsr_xmask;

    // UART
    wire                      uart_tx_start;
    wire [7:0]                uart_tx_data;
    wire                      uart_tx_busy;
    wire                      uart_tx_done;
    wire [7:0]                uart_rx_data;
    wire                      uart_rx_valid;

    // LED / race status
    wire                      led_g_ctrl;
    wire                      race_active;

    // ============================================================
    // 1. RO array
    // ============================================================
    ro_array u_ro_array (
        .enable (ro_enable),
        .ro_out (ro_pulses)
    );

    (* keep = "true" *) wire mux_a_raw = ro_pulses[mux_sel_a];
    (* keep = "true" *) wire mux_b_raw = ro_pulses[mux_sel_b];
    assign mux_a_out = mux_a_raw;
    assign mux_b_out = mux_b_raw;

    // Synchronous edge-detect counters. The original FPGA version clocked
    // these from the (asynchronous) RO nets; a register clocked by a data
    // net is not acceptable for the LibreLane flow, so the counters now
    // count rising edges of the selected RO output on the main clock.
    reg mux_a_d, mux_b_d;

    always @(posedge clk) begin
        if (!cnt_rst_n) begin
            mux_a_d <= 1'b0;
            cnt_a   <= {`CNT_WIDTH{1'b0}};
        end else begin
            mux_a_d <= mux_a_out;
            if (mux_a_out && !mux_a_d)
                cnt_a <= cnt_a + 1'b1;
        end
    end

    always @(posedge clk) begin
        if (!cnt_rst_n) begin
            mux_b_d <= 1'b0;
            cnt_b   <= {`CNT_WIDTH{1'b0}};
        end else begin
            mux_b_d <= mux_b_out;
            if (mux_b_out && !mux_b_d)
                cnt_b <= cnt_b + 1'b1;
        end
    end

    // ============================================================
    // 2. Arbiter switch chain (the strong-PUF core)
    // ============================================================
    arbiter_chain #(
        .STAGES (`ARB_STAGES),
        .IDX    (0)
    ) u_chain (
        .launch  (launch),
        .ch      (lfsr_state),
        .top_out (top_out),
        .bot_out (bot_out)
    );

    arbiter_cell u_arbiter (
        .top_in    (top_out),
        .bot_in    (bot_out),
        .arb_rst_n (arb_rst_n),
        .q         (arb_q)
    );

    // ============================================================
    // 3. Silicon power-up entropy bank (hybrid anchor)
    // ============================================================
    silicon_entropy #(
        .W (`SILICON_W)
    ) u_silicon_entropy (
        .clk  (clk),
        .bits (silicon_bits)
    );

    // ============================================================
    // 4. LFSR (challenge derivation + keystream)
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
    // 5. UART
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

    uart_rx u_uart_rx (
        .clk      (clk),
        .rst_n    (rst_n),
        .rx_pin   (uart_rx),
        .rx_data  (uart_rx_data),
        .rx_valid (uart_rx_valid)
    );

    // ============================================================
    // 6. PUF controller (FSM)
    // ============================================================
    puf_controller u_controller (
        .clk          (clk),
        .rst_n        (rst_n),
        .ro_enable    (ro_enable),
        .cnt_rst_n    (cnt_rst_n),
        .mux_sel_a    (mux_sel_a),
        .mux_sel_b    (mux_sel_b),
        .cnt_a_val    (cnt_a),
        .cnt_b_val    (cnt_b),
        .launch       (launch),
        .arb_rst_n    (arb_rst_n),
        .arb_q        (arb_q),
        .silicon_bits (silicon_bits),
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
        .uart_rx_data (uart_rx_data),
        .uart_rx_valid(uart_rx_valid),
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
