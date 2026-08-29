`ifndef ARBCHAIN_VH
`define ARBCHAIN_VH
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
endmodule
`endif