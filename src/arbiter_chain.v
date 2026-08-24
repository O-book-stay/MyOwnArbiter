`timescale 1ns/1ps
`include "puf_defines.v"

// ============================================================
// Arbiter switch chain for the iterative feedback strong PUF.
//
// NOTE: this file is the BEHAVIOURAL model used for RTL
// simulation only.  On silicon the switch chain is the symmetric
// hard macro `arbchain` (src/macro) which is hand-placed and
// routed with mirror-symmetric delay lines, guaranteeing that the
// race outcome is dominated by random process variation instead of
// systematic layout skew.
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
