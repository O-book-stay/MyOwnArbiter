`timescale 1ns/1ps
`ifdef USE_POWER_PINS
module arbchain (q, launch, arb_rst_n, ch, VPWR, VGND);
`else
module arbchain (q, launch, arb_rst_n, ch);
`endif
  output q; input launch; input arb_rst_n; input [15:0] ch;
  wire top_out, bot_out;
  arbiter_chain #(.STAGES(16), .IDX(0)) u_chain (.launch(launch), .ch(ch), .top_out(top_out), .bot_out(bot_out));
  arbiter_cell u_arbiter (.top_in(top_out), .bot_in(bot_out), .arb_rst_n(arb_rst_n), .q(q));
endmodule
