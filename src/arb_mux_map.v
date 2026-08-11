// Techmap template for arb_mux cells (arbiter switch chain).
//
// Referenced by SYNTH_EXTRA_MAPPING_FILE in src/config.json.
// The LibreLane flow runs `techmap -map arb_mux_map.v` after synthesis,
// replacing every preserved arb_mux cell with the physical
// sky130_fd_sc_hd__mux2_1 standard cell (power pins are connected
// automatically by the LibreLane power-connection step).

module arb_mux (
    input  wire a,
    input  wire b,
    input  wire s,
    output wire y
);
    sky130_fd_sc_hd__mux2_1 _mux (
        .A0 (a),
        .A1 (b),
        .S  (s),
        .X  (y)
    );
endmodule
