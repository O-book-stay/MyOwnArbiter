`timescale 1ns/1ps
// behavioural model of the arbchain macro (RTL simulation only)
module arbchain (
  q, launch, arb_rst_n, ch
);
  output q;
  input launch;
  input arb_rst_n;
  input [23:0] ch;

  wire top_out, bot_out;

  arbiter_chain #(.STAGES(24), .IDX(0)) u_chain (
    .launch(launch), .ch(ch), .top_out(top_out), .bot_out(bot_out)
  );

  arbiter_cell u_arbiter (
    .top_in(top_out), .bot_in(bot_out), .arb_rst_n(arb_rst_n), .q(q)
  );
endmodule
