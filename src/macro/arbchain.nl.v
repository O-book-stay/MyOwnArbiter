// gate-level netlist (pure structural - no continuous assigns)
`ifdef USE_POWER_PINS
`celldefine
module arbchain (
  output q, input launch, input arb_rst_n, input [15:0] ch,
  input VPWR, input VGND
);
`else
module arbchain (
  output q, input launch, input arb_rst_n, input [15:0] ch
);
`endif
  wire [16:0] top;
  wire [16:0] bot;
  sky130_fd_sc_hd__mux2_1 u_t0 (
    .A0(launch), .A1(launch), .S(ch[0]), .X(top[1]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b0 (
    .A0(launch), .A1(launch), .S(ch[0]), .X(bot[1]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t1 (
    .A0(top[1]), .A1(bot[1]), .S(ch[1]), .X(top[2]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b1 (
    .A0(bot[1]), .A1(top[1]), .S(ch[1]), .X(bot[2]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t2 (
    .A0(top[2]), .A1(bot[2]), .S(ch[2]), .X(top[3]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b2 (
    .A0(bot[2]), .A1(top[2]), .S(ch[2]), .X(bot[3]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t3 (
    .A0(top[3]), .A1(bot[3]), .S(ch[3]), .X(top[4]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b3 (
    .A0(bot[3]), .A1(top[3]), .S(ch[3]), .X(bot[4]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t4 (
    .A0(top[4]), .A1(bot[4]), .S(ch[4]), .X(top[5]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b4 (
    .A0(bot[4]), .A1(top[4]), .S(ch[4]), .X(bot[5]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t5 (
    .A0(top[5]), .A1(bot[5]), .S(ch[5]), .X(top[6]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b5 (
    .A0(bot[5]), .A1(top[5]), .S(ch[5]), .X(bot[6]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t6 (
    .A0(top[6]), .A1(bot[6]), .S(ch[6]), .X(top[7]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b6 (
    .A0(bot[6]), .A1(top[6]), .S(ch[6]), .X(bot[7]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t7 (
    .A0(top[7]), .A1(bot[7]), .S(ch[7]), .X(top[8]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b7 (
    .A0(bot[7]), .A1(top[7]), .S(ch[7]), .X(bot[8]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t8 (
    .A0(top[8]), .A1(bot[8]), .S(ch[8]), .X(top[9]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b8 (
    .A0(bot[8]), .A1(top[8]), .S(ch[8]), .X(bot[9]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t9 (
    .A0(top[9]), .A1(bot[9]), .S(ch[9]), .X(top[10]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b9 (
    .A0(bot[9]), .A1(top[9]), .S(ch[9]), .X(bot[10]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t10 (
    .A0(top[10]), .A1(bot[10]), .S(ch[10]), .X(top[11]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b10 (
    .A0(bot[10]), .A1(top[10]), .S(ch[10]), .X(bot[11]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t11 (
    .A0(top[11]), .A1(bot[11]), .S(ch[11]), .X(top[12]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b11 (
    .A0(bot[11]), .A1(top[11]), .S(ch[11]), .X(bot[12]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t12 (
    .A0(top[12]), .A1(bot[12]), .S(ch[12]), .X(top[13]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b12 (
    .A0(bot[12]), .A1(top[12]), .S(ch[12]), .X(bot[13]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t13 (
    .A0(top[13]), .A1(bot[13]), .S(ch[13]), .X(top[14]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b13 (
    .A0(bot[13]), .A1(top[13]), .S(ch[13]), .X(bot[14]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t14 (
    .A0(top[14]), .A1(bot[14]), .S(ch[14]), .X(top[15]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b14 (
    .A0(bot[14]), .A1(top[14]), .S(ch[14]), .X(bot[15]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t15 (
    .A0(top[15]), .A1(bot[15]), .S(ch[15]), .X(top[16]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b15 (
    .A0(bot[15]), .A1(top[15]), .S(ch[15]), .X(bot[16]) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__dlrtp_1 u_latch (
    .D(top[16]), .GATE(bot[16]), .RESET_B(arb_rst_n), .Q(q) , .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
endmodule
`endcelldefine
