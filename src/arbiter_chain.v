`timescale 1ns/1ps
`include "puf_defines.v"

// ============================================================
// Arbiter switch chain for the iterative feedback strong PUF.
//
// Each stage is two 2:1 muxes:
//   ch[i] = 0 : straight  (top_out=top_in , bot_out=bot_in)
//   ch[i] = 1 : cross     (top_out=bot_in , bot_out=top_in)
//
// A rising `launch` edge races down both paths; arbiter_cell latches
// which one arrives first. The race outcome on silicon depends on the
// real physical (placement + routing + process) delay asymmetry of the
// two paths - this is the PUF entropy.
//
// Synthesis preservation (critical):
//   * (* keep *) on EVERY stage net: Yosys treats each kept net as a
//     separate cone output, so the two paths cannot be merged.
//   * (* dont_touch *) on every arb_mux instance: the two race paths are
//     functionally identical, so opt/abc would otherwise fold each stage
//     mux into a buffer. dont_touch makes Yosys keep the mux cells.
//   * src/arb_mux_map.v (SYNTH_EXTRA_MAPPING_FILE) maps the preserved
//     arb_mux cells to the physical sky130_fd_sc_hd__mux2_1 cell.
//   * SYNTH_HIERARCHY_MODE=keep and SYNTH_SHARE_RESOURCES=false in
//     src/config.json keep the chain module hierarchical and prevent
//     resource sharing between the two paths.
//
// Simulation-only: per-stage transport delays (ifdef SIM) give the
// race something to resolve in RTL simulation; ignored in synthesis.
// ============================================================

(* keep_hierarchy = "true" *)
module arbiter_chain #(
    parameter STAGES = `ARB_STAGES,
    parameter IDX    = 0
) (
    input  wire            launch,
    input  wire [STAGES-1:0] ch,
    output wire            top_out,
    output wire            bot_out
);

    (* keep = "true" *) wire [STAGES:0] top;
    (* keep = "true" *) wire [STAGES:0] bot;

    genvar g;

    assign top[0] = launch;
    assign bot[0] = launch;

    generate
        for (g = 0; g < STAGES; g = g + 1) begin : stage
            (* keep = "true" *) wire t_mux, b_mux;
            wire tc = ch[g];

            // 2:1 mux, y = s ? b : a
            (* dont_touch = "true" *) arb_mux top_mux (
                .a (top[g]),
                .b (bot[g]),
                .s (tc),
                .y (t_mux)
            );
            (* dont_touch = "true" *) arb_mux bot_mux (
                .a (bot[g]),
                .b (top[g]),
                .s (tc),
                .y (b_mux)
            );

`ifdef SIM
            // When straight (c=0) the top path is slower -> bot tends to win;
            // when crossed (c=1) the bot path is slower  -> top tends to win.
            assign #(0.3 + (g % 8) * 0.01 + (IDX % 4) * 0.005 + (tc ? 0.0 : 0.20))
                top[g+1] = t_mux;
            assign #(0.3 + (g % 8) * 0.01 + (IDX % 4) * 0.005 + (tc ? 0.20 : 0.0))
                bot[g+1] = b_mux;
`else
            assign top[g+1] = t_mux;
            assign bot[g+1] = b_mux;
`endif
        end
    endgenerate

    assign top_out = top[STAGES];
    assign bot_out = bot[STAGES];

endmodule
