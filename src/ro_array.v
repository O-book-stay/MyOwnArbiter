`include "puf_defines.v"

module ro_array (
    input  wire                     enable,
    output wire [`RO_COUNT-1:0]     ro_out
);

    genvar i;
    generate
        for (i = 0; i < `RO_COUNT; i = i + 1) begin : ro_gen
            ro_cell #(.IDX(i)) ro_inst (
                .enable(enable),
                .ro_out(ro_out[i])
            );
        end
    endgenerate

endmodule
