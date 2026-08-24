`timescale 1ns/1ps

// ============================================================
// 2:1 multiplexer used by the arbiter switch chain.
//
// Instances of this module are marked (* dont_touch *) in
// arbiter_chain.v so that Yosys opt / abc never fold them away
// (the two race paths are functionally identical, so they would
// otherwise collapse to buffers). src/arb_mux_map.v provides the
// techmap template (referenced by SYNTH_EXTRA_MAPPING_FILE in
// src/config.json) that maps every arb_mux cell to the physical
// sky130_fd_sc_hd__mux2_1 standard cell.
// ============================================================

module arb_mux (
    input  wire a,
    input  wire b,
    input  wire s,
    output wire y
);
    assign y = s ? b : a;
endmodule
