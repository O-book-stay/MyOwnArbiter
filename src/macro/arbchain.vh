`ifdef USE_POWER_PINS
`celldefine
module arbchain (
  output q,
  input launch,
  input arb_rst_n,
  input [23:0] ch,
  input VPWR,
  input VGND
);
endmodule
`endcelldefine
`else
module arbchain (
  output q,
  input launch,
  input arb_rst_n,
  input [23:0] ch
);
endmodule
`endif
