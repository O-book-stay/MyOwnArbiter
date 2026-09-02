// ============================================================
// Gate-level structural netlist of the `arbchain` hard macro
// (src/macro/arbchain.gds, 17.28 x 82.0 um, sky130A).
//
// This replaces the former empty black-box stub: the tile GL
// netlist instantiates `arbchain` and gl_test compiles this file
// (test/Makefile GATES=yes), so an empty module left every
// macro-internal node (arb_q -> led_g -> uo_out) at X.
//
// Connectivity is transcribed 1:1 from the LVS-verified reference
// netlist runs/macro_lvs/arbchain_ref.spice ("Circuits match
// uniquely", 53 = 53 nets): 32x sky130_fd_sc_hd__mux2_1 (16
// switch stages, two mirrored columns) + 1x
// sky130_fd_sc_hd__dlrtp_1 (arbiter latch, async active-low reset).
//
// Topology (stage g in [0,16)):
//   top[0] = bot[0] = launch
//   top[g+1] = ch[g] ? bot[g] : top[g]   (top_XX: A0=top[g], A1=bot[g])
//   bot[g+1] = ch[g] ? top[g] : bot[g]   (bot_XX: A0=bot[g], A1=top[g])
//   q latches top[16] on the rising edge of bot[16] (dlrtp_1),
//   async-cleared by arb_rst_n.
//
// The race outcome is decided by the physical delay skew of the
// layout, which is exactly what this hard macro preserves. Do NOT
// synthesise this file; it is the simulation/integration view of
// the fixed geometry (config.json MACROS.arbchain.nl).
// ============================================================

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

  output            q;
  input             launch;
  input             arb_rst_n;
  input      [15:0] ch;
`ifdef USE_POWER_PINS
  inout             VPWR;
  inout             VGND;
`endif

  // race paths: top[1..16], bot[1..16] (top[0] / bot[0] == launch)
  wire [16:1] top;
  wire [16:1] bot;

  // stage 0: both A0 inputs tie straight to launch
  sky130_fd_sc_hd__mux2_1 top_00 (
    .A0(launch), .A1(launch), .S(ch[0]), .X(top[1])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_00 (
    .A0(launch), .A1(launch), .S(ch[0]), .X(bot[1])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_01 (
    .A0(top[1]), .A1(bot[1]), .S(ch[1]), .X(top[2])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_01 (
    .A0(bot[1]), .A1(top[1]), .S(ch[1]), .X(bot[2])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_02 (
    .A0(top[2]), .A1(bot[2]), .S(ch[2]), .X(top[3])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_02 (
    .A0(bot[2]), .A1(top[2]), .S(ch[2]), .X(bot[3])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_03 (
    .A0(top[3]), .A1(bot[3]), .S(ch[3]), .X(top[4])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_03 (
    .A0(bot[3]), .A1(top[3]), .S(ch[3]), .X(bot[4])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_04 (
    .A0(top[4]), .A1(bot[4]), .S(ch[4]), .X(top[5])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_04 (
    .A0(bot[4]), .A1(top[4]), .S(ch[4]), .X(bot[5])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_05 (
    .A0(top[5]), .A1(bot[5]), .S(ch[5]), .X(top[6])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_05 (
    .A0(bot[5]), .A1(top[5]), .S(ch[5]), .X(bot[6])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_06 (
    .A0(top[6]), .A1(bot[6]), .S(ch[6]), .X(top[7])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_06 (
    .A0(bot[6]), .A1(top[6]), .S(ch[6]), .X(bot[7])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_07 (
    .A0(top[7]), .A1(bot[7]), .S(ch[7]), .X(top[8])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_07 (
    .A0(bot[7]), .A1(top[7]), .S(ch[7]), .X(bot[8])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_08 (
    .A0(top[8]), .A1(bot[8]), .S(ch[8]), .X(top[9])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_08 (
    .A0(bot[8]), .A1(top[8]), .S(ch[8]), .X(bot[9])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_09 (
    .A0(top[9]), .A1(bot[9]), .S(ch[9]), .X(top[10])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_09 (
    .A0(bot[9]), .A1(top[9]), .S(ch[9]), .X(bot[10])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_10 (
    .A0(top[10]), .A1(bot[10]), .S(ch[10]), .X(top[11])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_10 (
    .A0(bot[10]), .A1(top[10]), .S(ch[10]), .X(bot[11])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_11 (
    .A0(top[11]), .A1(bot[11]), .S(ch[11]), .X(top[12])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_11 (
    .A0(bot[11]), .A1(top[11]), .S(ch[11]), .X(bot[12])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_12 (
    .A0(top[12]), .A1(bot[12]), .S(ch[12]), .X(top[13])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_12 (
    .A0(bot[12]), .A1(top[12]), .S(ch[12]), .X(bot[13])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_13 (
    .A0(top[13]), .A1(bot[13]), .S(ch[13]), .X(top[14])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_13 (
    .A0(bot[13]), .A1(top[13]), .S(ch[13]), .X(bot[14])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_14 (
    .A0(top[14]), .A1(bot[14]), .S(ch[14]), .X(top[15])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_14 (
    .A0(bot[14]), .A1(top[14]), .S(ch[14]), .X(bot[15])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  sky130_fd_sc_hd__mux2_1 top_15 (
    .A0(top[15]), .A1(bot[15]), .S(ch[15]), .X(top[16])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );
  sky130_fd_sc_hd__mux2_1 bot_15 (
    .A0(bot[15]), .A1(top[15]), .S(ch[15]), .X(bot[16])
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

  // arbiter latch: samples top[16] on the rising edge of bot[16]
  sky130_fd_sc_hd__dlrtp_1 arb (
    .D(top[16]), .GATE(bot[16]), .RESET_B(arb_rst_n), .Q(q)
`ifdef USE_POWER_PINS
    , .VPB(VPWR), .VNB(VGND), .VPWR(VPWR), .VGND(VGND)
`endif
  );

endmodule
