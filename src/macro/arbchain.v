`timescale 1ns/1ps
module arbchain (
    output            q,
    input             launch,
    input             arb_rst_n,
    input      [15:0] ch
`ifdef USE_POWER_PINS
    ,
    inout             VPWR,
    inout             VGND
`endif
);
  wire top_out, bot_out;
  arbiter_chain #(.STAGES(16), .IDX(0)) u_chain (
      .launch (launch),
      .ch     (ch),
      .top_out(top_out),
      .bot_out(bot_out)
  );
  arbiter_cell u_arbiter (
      .top_in   (top_out),
      .bot_in   (bot_out),
      .arb_rst_n(arb_rst_n),
      .q        (q)
  );
endmodule