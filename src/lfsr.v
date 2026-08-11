`timescale 1ns/1ps

// ============================================================
// Fibonacci-style LFSR used for:
//   * bootstrap challenge derivation
//   * main-loop challenge derivation (response bits folded back in)
//   * keystream generation for the final output mixing
//
// Shift-left; the new LSB is the XOR of a few tapped bits plus an
// optional injected bit (inject_bit). `load` has priority over `en`.
// ============================================================

module lfsr #(
    parameter W = 48
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

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            s <= {W{1'b0}};
        else if (load)
            s <= seed;
        else if (en)
            s <= ({s[W-2:0],
                   s[W-1] ^ s[W-2] ^ s[W-7] ^ s[W-13] ^ s[W-21] ^ s[W-33] ^ inject_bit})
                 ^ xmask;
    end

    assign state = s;

endmodule
