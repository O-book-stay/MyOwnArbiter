`timescale 1ns/1ps
`include "puf_defines.v"

// ============================================================
// Silicon power-up entropy bank (hybrid PUF anchor).
//
// A bank of flip-flops with NO reset, holding their own value:
// on real silicon (SKY130) these registers power up in a random but
// stable state determined by process variation - a power-up PUF.
//
// There is deliberately NO `initial` block in the RTL: the LibreLane
// flow must never be asked to map FF init values. Simulation seeds
// the bank directly through the testbench hierarchy
// (dut.u_puf_top.u_silicon_entropy.st in cocotb), keeping the RTL
// deterministic in simulation while remaining physically random on
// silicon.
// ============================================================

module silicon_entropy #(
    parameter W = `SILICON_W
) (
    input  wire         clk,
    output wire [W-1:0] bits
);

    (* keep = "true" *) reg [W-1:0] st;

    always @(posedge clk) begin
        st <= st;
    end

    assign bits = st;

endmodule
