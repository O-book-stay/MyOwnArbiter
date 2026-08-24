`timescale 1ns/1ps

// ============================================================
// Arbiter cell: latches whether the TOP path arrived before the
// BOTTOM path. Q=1 -> top first, Q=0 -> bottom first.
//
// The BOTTOM path is used as the clock and the TOP path as the data
// input: whichever signal arrives first at the sampling instant wins.
// This is the race-resolution point of the arbiter PUF and it must
// keep working even though `bot_in` is a combinational (data) net.
//
// Ported from the Gowin DFFC primitive to plain behavioural Verilog;
// on SKY130 the synthesizer maps this to a standard D flip-flop with
// asynchronous clear (clocked by the data net bot_in).
// ============================================================

module arbiter_cell (
    input  wire top_in,
    input  wire bot_in,
    input  wire arb_rst_n,
    output wire q
);

    reg q_r;

    always @(posedge bot_in or negedge arb_rst_n) begin
        if (!arb_rst_n)
            q_r <= 1'b0;
        else
            q_r <= top_in;
    end

    assign q = q_r;

endmodule
