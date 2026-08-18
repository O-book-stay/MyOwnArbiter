`include "puf_defines.v"

// ============================================================
// Iterative-feedback arbiter strong PUF controller.
//
// Flow per query (8-hex-char challenge -> 8-hex-char response):
//   S_RX_CHALLENGE : collect 8 hex chars -> challenge[31:0]
//   S_BOOT_SETUP   : seed LFSR with the public bootstrap seed
//   bootstrap      : BOOT_K rounds, VOTE races each (majority vote),
//                    hidden r0[BOOT_K-1:0] = voted bits, LFSR fed back
//   main_seed      = hidden ^ fold(challenge)
//   main loop      : RESP_BITS rounds; per round challenge = LFSR
//                    state, VOTE races, majority vote -> bit; the
//                    bit is folded back into the LFSR and is mixed
//                    inline with the keystream:
//                        R[i] = vote ^ lfsr[0] ^ parity(c, lfsr)
//                    every 4 finished bits one hex char goes out on
//                    the UART (racing pauses while the byte shifts)
//   S_DONE         : back to challenge-wait
//
// The arbiter race (launch -> ARB_STAGES-stage chain -> arbiter
// latch) is the only entropy source.
// ============================================================

module puf_controller (
    input  wire                     clk,
    input  wire                     rst_n,

    // Arbiter chain control
    output reg                      launch,
    output reg                      arb_rst_n,
    input  wire                     arb_q,

    // LFSR
    output reg                      lfsr_load,
    output reg                      lfsr_en,
    output reg                      lfsr_inject,
    output reg  [`ARB_STAGES-1:0]   lfsr_seed,
    input  wire [`ARB_STAGES-1:0]   lfsr_state,
    output wire [`ARB_STAGES-1:0]   lfsr_xmask,

    // UART interface
    output reg                      uart_start,
    output reg  [7:0]               uart_data,
    input  wire                     uart_busy,
    input  wire                     uart_done,

    // UART RX (challenge input)
    input  wire [7:0]               uart_rx_data,
    input  wire                     uart_rx_valid,

    // Status LEDs
    output reg                      led_r,
    output reg                      led_g,
    output reg                      led_b,

    // Race activity flag: high while an arbiter race is in flight.  The top
    // level mirrors arb_q onto led_g while this is high, which gives the
    // synthesizer a direct combinational path from arb_q to a primary
    // output - without it the optimizer prunes the arbiter as "dangling".
    output reg                      race_active
);

    // ============================================================
    // State machine (S_DONE must stay 4'd9 for tb compatibility)
    // ============================================================
    localparam S_IDLE         = 4'd0;
    localparam S_RX_CHALLENGE = 4'd1;
    localparam S_SEND_WAIT    = 4'd8;
    localparam S_DONE         = 4'd9;
    localparam S_RACE_RESET   = 4'd10;
    localparam S_RACE_LAUNCH  = 4'd11;
    localparam S_RACE_SETTLE  = 4'd12;
    localparam S_RACE_READ    = 4'd13;
    localparam S_BOOT_SETUP   = 4'd15;

    localparam PH_BOOT = 2'd0;
    localparam PH_MAIN = 2'd2;

    reg [3:0] state;

    // ============================================================
    // Timing / counters
    // ============================================================
    reg [5:0]  race_timer;
    reg [5:0]  bit_idx;       // bootstrap 0..BOOT_K-1, main 0..RESP_BITS-1
    reg [1:0]  race_cnt;      // 0..VOTE-1 within a bit
    reg [1:0]  vote_acc;      // majority accumulator
    reg        race_bit_d;    // sampled arbiter output
    reg [1:0]  phase;         // PH_BOOT / PH_MAIN

    // ============================================================
    // Challenge / response state
    // ============================================================
    reg [`RESP_BITS-1:0] challenge;
    reg [2:0]            challenge_idx;
    reg [`BOOT_K-1:0]     r0;         // bootstrap hidden part
    reg [3:0]            nibble_acc; // response nibble being assembled
    reg [2:0]            uart_byte_idx;

    // ============================================================
    // Seeds / constants / mixing
    // ============================================================
    wire [`ARB_STAGES-1:0] BS_SEED = `ARB_STAGES'hE5A3C7;

    wire [`ARB_STAGES-1:0] hidden    = {{`ARB_STAGES-`BOOT_K{1'b0}}, r0};
    wire [`ARB_STAGES-1:0] main_seed = hidden ^ fold_fn(challenge);

    // XOR-fold the (possibly wider) challenge into ARB_STAGES bits so every
    // challenge bit contributes to the seed, robust for any RESP_BITS.
    function automatic [`ARB_STAGES-1:0] fold_fn;
        input [`RESP_BITS-1:0] c;
        integer i;
        begin
            fold_fn = {`ARB_STAGES{1'b0}};
            for (i = 0; i < `RESP_BITS; i = i + 1)
                fold_fn[i % `ARB_STAGES] = fold_fn[i % `ARB_STAGES] ^ c[i];
        end
    endfunction

    // Dense mixing: during the main loop the challenge fold is XORed
    // into the LFSR state on every step, so a single challenge bit
    // diffuses to a growing run of positions (good avalanche).
    assign lfsr_xmask = (phase == PH_MAIN) ? fold_fn(challenge) : {`ARB_STAGES{1'b0}};

    // Secret-mask-gated parity of the challenge: flips ~half the response
    // bits when a single challenge bit flips (avalanche booster).
    function parity_mask;
        input [`RESP_BITS-1:0] c;
        input [`ARB_STAGES-1:0] s;
        integer i;
        begin
            parity_mask = 1'b0;
            for (i = 0; i < `ARB_STAGES; i = i + 1)
                if (i < `RESP_BITS)
                    parity_mask = parity_mask ^ (c[i] & s[i]);
        end
    endfunction

    // Majority vote of the current bit over the VOTE races.
    wire voted = (vote_acc + race_bit_d) >= 2;

    // Inline output mixing: race bit XOR keystream XOR challenge parity.
    wire [3:0] nib_next = {nibble_acc[2:0],
                           voted ^ lfsr_state[0]
                                ^ parity_mask(challenge, lfsr_state)};

    // ============================================================
    // Nibble / hex helpers
    // ============================================================
    function [7:0] nibble2hex;
        input [3:0] nib;
        begin
            nibble2hex = (nib < 10) ? (8'h30 + nib) : (8'h37 + nib);
        end
    endfunction

    function is_hex_char;
        input [7:0] b;
        begin
            is_hex_char = ((b >= 8'h30 && b <= 8'h39) ||
                           (b >= 8'h41 && b <= 8'h46) ||
                           (b >= 8'h61 && b <= 8'h66));
        end
    endfunction

    function [3:0] hex2nibble;
        input [7:0] b;
        begin
            case (b)
                8'h30, 8'h31, 8'h32, 8'h33, 8'h34,
                8'h35, 8'h36, 8'h37, 8'h38, 8'h39: hex2nibble = b[3:0];
                8'h41, 8'h42, 8'h43, 8'h44, 8'h45, 8'h46: hex2nibble = b[3:0] + 4'h9;
                8'h61, 8'h62, 8'h63, 8'h64, 8'h65, 8'h66: hex2nibble = b[3:0] + 4'h9;
                default: hex2nibble = 4'h0;
            endcase
        end
    endfunction

    // ============================================================
    // FSM
    // ============================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            launch        <= 1'b0;
            arb_rst_n     <= 1'b0;
            lfsr_load     <= 1'b0;
            lfsr_en       <= 1'b0;
            lfsr_inject   <= 1'b0;
            lfsr_seed     <= {`ARB_STAGES{1'b0}};
            uart_start    <= 1'b0;
            uart_data     <= 8'd0;
            led_r         <= 1'b1;
            led_g         <= 1'b0;
            led_b         <= 1'b0;
            race_active   <= 1'b0;
            race_timer    <= 6'd0;
            bit_idx       <= 6'd0;
            race_cnt      <= 2'd0;
            vote_acc      <= 2'd0;
            race_bit_d    <= 1'b0;
            phase         <= PH_BOOT;
            challenge     <= {`RESP_BITS{1'b0}};
            challenge_idx <= 3'd0;
            r0            <= {`BOOT_K{1'b0}};
            nibble_acc    <= 4'd0;
            uart_byte_idx <= 3'd0;
        end else begin
            // Defaults (overridden by state actions below)
            uart_start  <= 1'b0;
            lfsr_load   <= 1'b0;
            lfsr_en     <= 1'b0;
            lfsr_inject <= 1'b0;
            race_active <= 1'b0;

            case (state)

                // Reset entry: wait for an 8-hex-char challenge
                S_IDLE: begin
                    led_r         <= 1'b0;
                    led_g         <= 1'b0;
                    led_b         <= 1'b1;
                    launch        <= 1'b0;
                    arb_rst_n     <= 1'b0;
                    phase         <= PH_BOOT;
                    bit_idx       <= 6'd0;
                    race_cnt      <= 2'd0;
                    vote_acc      <= 2'd0;
                    nibble_acc    <= 4'd0;
                    challenge_idx <= 3'd0;
                    uart_byte_idx <= 3'd0;
                    state         <= S_RX_CHALLENGE;
                end

                S_RX_CHALLENGE: begin
                    led_b <= 1'b1;
                    if (uart_rx_valid && is_hex_char(uart_rx_data)) begin
                        challenge[`RESP_BITS - 1 - challenge_idx*4 -: 4] <= hex2nibble(uart_rx_data);
                        if (challenge_idx >= `RESP_BITS/4 - 1) begin
                            challenge_idx <= 3'd0;
                            state         <= S_BOOT_SETUP;
                        end else begin
                            challenge_idx <= challenge_idx + 1'b1;
                        end
                    end
                end

                // Seed LFSR for bootstrap (PH_BOOT) or for the main loop (PH_MAIN)
                S_BOOT_SETUP: begin
                    led_r      <= 1'b1;
                    led_g      <= 1'b0;
                    led_b      <= 1'b0;
                    lfsr_load  <= 1'b1;
                    lfsr_seed  <= (phase == PH_BOOT) ? BS_SEED : main_seed;
                    launch     <= 1'b0;
                    arb_rst_n  <= 1'b0;
                    if (phase == PH_BOOT) begin
                        bit_idx  <= 6'd0;
                        race_cnt <= 2'd0;
                        vote_acc <= 2'd0;
                    end
                    state <= S_RACE_RESET;
                end

                // ------------------------------------------------------------------
                // Race states (used by both bootstrap and main loop)
                // ------------------------------------------------------------------
                S_RACE_RESET: begin
                    led_r      <= 1'b1;
                    led_g      <= 1'b0;
                    led_b      <= 1'b0;
                    launch     <= 1'b0;
                    arb_rst_n  <= 1'b0;
                    race_timer <= 6'd0;
                    race_active <= 1'b1;
                    state       <= S_RACE_LAUNCH;
                end

                S_RACE_LAUNCH: begin
                    arb_rst_n   <= 1'b1;
                    launch      <= 1'b1;
                    race_timer  <= race_timer + 8'd1;
                    race_active <= 1'b1;
                    if (race_timer >= `ARB_SETTLE_CYCLES - 1) begin
                        race_timer <= 6'd0;
                        state      <= S_RACE_SETTLE;
                    end
                end

                S_RACE_SETTLE: begin
                    launch      <= 1'b0;
                    race_timer  <= race_timer + 8'd1;
                    race_active <= 1'b1;
                    if (race_timer >= `ARB_SETTLE_CYCLES - 1) begin
                        race_timer <= 6'd0;
                        state      <= S_RACE_READ;
                    end
                end

                S_RACE_READ: begin
                    // Sample the arbiter every cycle of this state: an
                    // unconditional load keeps the arb_q dependency visible
                    // to the synthesizer.
                    race_bit_d  <= arb_q;
                    race_timer  <= race_timer + 8'd1;
                    race_active <= 1'b1;
                    if (race_timer == 8'd3) begin
                        // majority vote over VOTE races of the current bit
                        if (race_cnt == `VOTE - 1) begin
                            // last race: bit = (vote_acc + race_bit_d) >= 2
                            lfsr_inject <= voted;
                            lfsr_en     <= 1'b1;
                            if (phase == PH_BOOT) begin
                                // shift-left write (variable-indexed writes
                                // to wide regs confuse the synthesizer's
                                // liveness analysis and cause it to sweep
                                // the arbiter chain as dangling)
                                r0 <= {r0[`BOOT_K-2:0], voted};
                                if (bit_idx == `BOOT_K - 1) begin
                                    bit_idx  <= 6'd0;
                                    race_cnt <= 2'd0;
                                    vote_acc <= 2'd0;
                                    phase    <= PH_MAIN;
                                    state    <= S_BOOT_SETUP; // re-seed with main_seed
                                end else begin
                                    bit_idx  <= bit_idx + 6'd1;
                                    race_cnt <= 2'd0;
                                    vote_acc <= 2'd0;
                                    state    <= S_RACE_RESET;
                                end
                            end else begin  // PH_MAIN
                                nibble_acc <= nib_next;
                                if (bit_idx[1:0] == 2'd3) begin
                                    // nibble complete: send it and pause racing
                                    uart_data  <= nibble2hex(nib_next);
                                    uart_start <= 1'b1;
                                    led_r      <= 1'b0;
                                    led_g      <= 1'b1;
                                    led_b      <= 1'b1;
                                end
                                if (bit_idx == `RESP_BITS - 1) begin
                                    bit_idx  <= 6'd0;
                                    race_cnt <= 2'd0;
                                    vote_acc <= 2'd0;
                                    // RESP_BITS is a multiple of 4, so the
                                    // last bit always completes a nibble
                                    state <= S_SEND_WAIT;
                                end else begin
                                    bit_idx  <= bit_idx + 6'd1;
                                    race_cnt <= 2'd0;
                                    vote_acc <= 2'd0;
                                    state    <= (bit_idx[1:0] == 2'd3)
                                              ? S_SEND_WAIT : S_RACE_RESET;
                                end
                            end
                        end else begin
                            race_cnt <= race_cnt + 2'd1;
                            vote_acc <= vote_acc + race_bit_d;  // accumulate the vote
                            state    <= S_RACE_RESET;
                        end
                    end
                end

                // ------------------------------------------------------------------
                // UART send: wait for the shifting nibble char to finish
                // ------------------------------------------------------------------
                S_SEND_WAIT: begin
                    led_r <= 1'b0;
                    led_g <= 1'b1;
                    led_b <= 1'b1;
                    if (uart_done) begin
                        if (uart_byte_idx >= `RESP_BITS / 4 - 1) begin
                            uart_byte_idx <= 3'd0;
                            state         <= S_DONE;
                        end else begin
                            uart_byte_idx <= uart_byte_idx + 1'b1;
                            state         <= S_RACE_RESET;
                        end
                    end
                end

                S_DONE: begin
                    led_r <= 1'b0;
                    led_g <= 1'b1;
                    led_b <= 1'b0;
                    state <= S_RX_CHALLENGE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
