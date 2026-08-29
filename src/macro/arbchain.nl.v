`timescale 1ns/1ps
module arbchain (
    q,
    launch,
    arb_rst_n,
    ch
`ifdef USE_POWER_PINS
    ,
    VPWR,
    VGND
`endif
);
  output q;
  input  launch;
  input  arb_rst_n;
  input  [15:0] ch;
`ifdef USE_POWER_PINS
  inout  VPWR;
  inout  VGND;
`endif
endmodule