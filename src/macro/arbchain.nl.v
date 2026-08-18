// gate-level netlist of the arbchain macro (generated)
module arbchain (
  output q,
  input launch,
  input arb_rst_n,
  input [23:0] ch,
  input VPWR,
  input VGND
);
  wire [24:0] top;
  wire [24:0] bot;
  wire d, gate;
  assign top[0] = launch;
  assign bot[0] = launch;
  sky130_fd_sc_hd__mux2_1 u_t0 (
    .A0(top[0]), .A1(bot[0]), .S(ch[0]), .X(top[1]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b0 (
    .A0(bot[0]), .A1(top[0]), .S(ch[0]), .X(bot[1]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t1 (
    .A0(top[1]), .A1(bot[1]), .S(ch[1]), .X(top[2]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b1 (
    .A0(bot[1]), .A1(top[1]), .S(ch[1]), .X(bot[2]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t2 (
    .A0(top[2]), .A1(bot[2]), .S(ch[2]), .X(top[3]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b2 (
    .A0(bot[2]), .A1(top[2]), .S(ch[2]), .X(bot[3]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t3 (
    .A0(top[3]), .A1(bot[3]), .S(ch[3]), .X(top[4]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b3 (
    .A0(bot[3]), .A1(top[3]), .S(ch[3]), .X(bot[4]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t4 (
    .A0(top[4]), .A1(bot[4]), .S(ch[4]), .X(top[5]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b4 (
    .A0(bot[4]), .A1(top[4]), .S(ch[4]), .X(bot[5]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t5 (
    .A0(top[5]), .A1(bot[5]), .S(ch[5]), .X(top[6]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b5 (
    .A0(bot[5]), .A1(top[5]), .S(ch[5]), .X(bot[6]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t6 (
    .A0(top[6]), .A1(bot[6]), .S(ch[6]), .X(top[7]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b6 (
    .A0(bot[6]), .A1(top[6]), .S(ch[6]), .X(bot[7]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t7 (
    .A0(top[7]), .A1(bot[7]), .S(ch[7]), .X(top[8]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b7 (
    .A0(bot[7]), .A1(top[7]), .S(ch[7]), .X(bot[8]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t8 (
    .A0(top[8]), .A1(bot[8]), .S(ch[8]), .X(top[9]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b8 (
    .A0(bot[8]), .A1(top[8]), .S(ch[8]), .X(bot[9]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t9 (
    .A0(top[9]), .A1(bot[9]), .S(ch[9]), .X(top[10]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b9 (
    .A0(bot[9]), .A1(top[9]), .S(ch[9]), .X(bot[10]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t10 (
    .A0(top[10]), .A1(bot[10]), .S(ch[10]), .X(top[11]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b10 (
    .A0(bot[10]), .A1(top[10]), .S(ch[10]), .X(bot[11]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t11 (
    .A0(top[11]), .A1(bot[11]), .S(ch[11]), .X(top[12]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b11 (
    .A0(bot[11]), .A1(top[11]), .S(ch[11]), .X(bot[12]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t12 (
    .A0(top[12]), .A1(bot[12]), .S(ch[12]), .X(top[13]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b12 (
    .A0(bot[12]), .A1(top[12]), .S(ch[12]), .X(bot[13]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t13 (
    .A0(top[13]), .A1(bot[13]), .S(ch[13]), .X(top[14]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b13 (
    .A0(bot[13]), .A1(top[13]), .S(ch[13]), .X(bot[14]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t14 (
    .A0(top[14]), .A1(bot[14]), .S(ch[14]), .X(top[15]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b14 (
    .A0(bot[14]), .A1(top[14]), .S(ch[14]), .X(bot[15]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t15 (
    .A0(top[15]), .A1(bot[15]), .S(ch[15]), .X(top[16]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b15 (
    .A0(bot[15]), .A1(top[15]), .S(ch[15]), .X(bot[16]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t16 (
    .A0(top[16]), .A1(bot[16]), .S(ch[16]), .X(top[17]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b16 (
    .A0(bot[16]), .A1(top[16]), .S(ch[16]), .X(bot[17]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t17 (
    .A0(top[17]), .A1(bot[17]), .S(ch[17]), .X(top[18]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b17 (
    .A0(bot[17]), .A1(top[17]), .S(ch[17]), .X(bot[18]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t18 (
    .A0(top[18]), .A1(bot[18]), .S(ch[18]), .X(top[19]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b18 (
    .A0(bot[18]), .A1(top[18]), .S(ch[18]), .X(bot[19]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t19 (
    .A0(top[19]), .A1(bot[19]), .S(ch[19]), .X(top[20]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b19 (
    .A0(bot[19]), .A1(top[19]), .S(ch[19]), .X(bot[20]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t20 (
    .A0(top[20]), .A1(bot[20]), .S(ch[20]), .X(top[21]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b20 (
    .A0(bot[20]), .A1(top[20]), .S(ch[20]), .X(bot[21]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t21 (
    .A0(top[21]), .A1(bot[21]), .S(ch[21]), .X(top[22]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b21 (
    .A0(bot[21]), .A1(top[21]), .S(ch[21]), .X(bot[22]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t22 (
    .A0(top[22]), .A1(bot[22]), .S(ch[22]), .X(top[23]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b22 (
    .A0(bot[22]), .A1(top[22]), .S(ch[22]), .X(bot[23]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_t23 (
    .A0(top[23]), .A1(bot[23]), .S(ch[23]), .X(top[24]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  sky130_fd_sc_hd__mux2_1 u_b23 (
    .A0(bot[23]), .A1(top[23]), .S(ch[23]), .X(bot[24]),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
  assign d = top[24];
  assign gate = bot[24];
  sky130_fd_sc_hd__dlrtp_1 u_latch (
    .D(d), .GATE(gate), .RESET_B(arb_rst_n), .Q(q),
    .VPWR(VPWR), .VGND(VGND), .VPB(VPWR), .VNB(VGND)
  );
endmodule
