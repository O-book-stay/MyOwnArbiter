`timescale 1ns/1ps
`include "puf_defines.v"

// ============================================================
// Fibonacci-style LFSR used for:
//   * bootstrap challenge derivation
//   * main-loop challenge derivation (response bits folded back in)
//   * keystream bits for the inline output mixing
//
// Shift-left; the new LSB is the XOR of the tapped bits plus an
// optional injected bit (inject_bit). `load` has priority over `en`.
//
// Tap set (XAPP052 maximal-length polynomials):
//   W = 64 : taps {64, 63, 61, 60} -> s[63] ^ s[62] ^ s[60] ^ s[59]
//   W = 32 : taps {32, 22, 2, 1}   -> s[31] ^ s[21] ^ s[1] ^ s[0]
//   W = 29 : taps {29, 2}          -> s[28] ^ s[1]
// The legacy 6-tap set is only used for other wide words; the
// generate block picks the tap set automatically.
// ============================================================

module lfsr #(
    parameter W = `ARB_STAGES
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         load,
    input  wire         en,
    input  wire         inject_bit,
    input  wire [W-1:0] xmask,   // XOR mask applied every step (challenge fold)
    input  wire [W-1:0] seed,
    output wire [W-1:0] state
);

    reg [W-1:0] s;
    wire        feedback;

    generate
        if (W == 64) begin : g_taps_64
            assign feedback = s[63] ^ s[62] ^ s[60] ^ s[59];
        end else if (W == 32) begin : g_taps_32
            assign feedback = s[31] ^ s[21] ^ s[1] ^ s[0];
        end else if (W >= 34) begin : g_taps_legacy
            // original 6-tap set (requires W >= 34)
            assign feedback = s[W-1] ^ s[W-2] ^ s[W-7] ^ s[W-13] ^ s[W-21] ^ s[W-33];
        end else begin : g_taps_xapp052
            // taps {W, 2}: maximal-length for W = 29
            assign feedback = s[W-1] ^ s[1];
        end
    endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            s <= {W{1'b0}};
        else if (load)
            s <= seed;
        else if (en)
            s <= ({s[W-2:0], feedback ^ inject_bit}) ^ xmask;
    end

    assign state = s;

endmodule
