`include "puf_defines.v"

module uart_rx (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx_pin,
    output reg  [7:0] rx_data,
    output reg        rx_valid
);

    localparam BIT_PERIOD = `BIT_PERIOD;
    localparam CNT_WIDTH  = 10;

    reg [1:0]        rx_sync;
    wire             rx_prev = rx_sync[1];
    reg              rx_idle;
    reg [CNT_WIDTH-1:0] clk_cnt;
    reg [3:0]        bit_idx;   // 0=start .. 8=data .. 9=stop
    reg [7:0]        sh_reg;

    // ------------------------------------------------------------------
    // 2-FF synchronizer for the async RX line
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            rx_sync <= 2'b11;
        else
            rx_sync <= {rx_sync[0], rx_pin};
    end

    // ------------------------------------------------------------------
    // Receive state machine (8-N-1, sample at mid-bit)
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_data  <= 8'h00;
            rx_valid <= 1'b0;
            rx_idle  <= 1'b1;
            clk_cnt  <= 0;
            bit_idx  <= 0;
            sh_reg   <= 8'h00;
        end else begin
            rx_valid <= 1'b0;

            if (rx_idle) begin
                clk_cnt <= 0;
                bit_idx <= 0;
                // Start bit = falling edge while idle
                if (!rx_sync[0] && rx_prev)
                    rx_idle <= 1'b0;
            end else begin
                clk_cnt <= clk_cnt + 1'b1;

                // Start-bit width check: a noise glitch shorter than 3/4 of
                // a bit period must not be accepted as a start bit. If the
                // line is already high at 3/4 of the start bit, abort and
                // wait for the next falling edge.
                if (bit_idx == 4'd0 && clk_cnt == (BIT_PERIOD * 3 / 4))
                    if (rx_sync[0])
                        rx_idle <= 1'b1;

                // Sample each bit at mid-bit (LSB first)
                if (clk_cnt == (BIT_PERIOD >> 1)) begin
                    case (bit_idx)
                        4'd1: sh_reg[0] <= rx_sync[0];
                        4'd2: sh_reg[1] <= rx_sync[0];
                        4'd3: sh_reg[2] <= rx_sync[0];
                        4'd4: sh_reg[3] <= rx_sync[0];
                        4'd5: sh_reg[4] <= rx_sync[0];
                        4'd6: sh_reg[5] <= rx_sync[0];
                        4'd7: sh_reg[6] <= rx_sync[0];
                        4'd8: sh_reg[7] <= rx_sync[0];
                        default: ;
                    endcase
                end

                // End of a bit period
                if (clk_cnt == (BIT_PERIOD - 1)) begin
                    clk_cnt <= 0;
                    if (bit_idx == 4'd9) begin
                        if (rx_sync[0]) begin
                            rx_data  <= sh_reg;
                            rx_valid <= 1'b1;
                        end
                        rx_idle <= 1'b1;
                        bit_idx <= 4'd0;
                    end else begin
                        bit_idx <= bit_idx + 4'd1;
                    end
                end
            end
        end
    end

endmodule
