`timescale 1ns/1ps

// ============================================================
// Ring Oscillator cell, ASIC-portable version.
//
// Original Gowin implementation instantiated five LUT4 primitives
// (NAND + 4 inverters) with the feedback loop forming an oscillator.
// Combinational loops are illegal in the Tiny Tapeout / LibreLane flow,
// so the oscillator feedback only exists under `ifdef SIM (with
// transport delays so iverilog actually oscillates).
//
// The synthesis (non-SIM) path is a loop-free combinational replica:
// identical gate structure, no feedback, so the design stays legal.
// RO entropy is not used on silicon; the real entropy comes from the
// arbiter race plus the silicon power-up FF bank (silicon_entropy.v).
// ============================================================

module ro_cell #(
    parameter IDX = 0
) (
    input  wire enable,
    output wire ro_out
);

`ifdef SIM
    // Simulation-only oscillator: NAND + 4 inverters with per-cell delay
    (* keep = "true" *) wire [4:0] w;
    wire fb;
    assign #(2.0 + (IDX % 8) * 0.1) fb = w[4];

    assign w[0] = ~(enable & fb);   // NAND stage
    assign w[1] = ~w[0];            // inverter
    assign w[2] = ~w[1];            // inverter
    assign w[3] = ~w[2];            // inverter
    assign w[4] = ~w[3];            // inverter

    assign ro_out = fb;
`else
    // Synthesis: loop-free replica of the 5-stage gate chain.
    // No feedback: the chain is purely combinational and never oscillates.
    (* keep = "true" *) wire [4:0] w;
    assign w[0] = ~(enable & enable);
    assign w[1] = ~w[0];
    assign w[2] = ~w[1];
    assign w[3] = ~w[2];
    assign w[4] = ~w[3];

    assign ro_out = w[4];
`endif

endmodule
