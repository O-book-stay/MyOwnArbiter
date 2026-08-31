`include "cpu_defines.v"

module uart_tx (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         tx_start,
    input  wire [7:0]   data_in,
    output reg          tx_pin,
    output reg          tx_busy,
    output reg          tx_done
);

    localparam BIT_PERIOD = `BIT_PERIOD;
    localparam CNT_WIDTH  = 10;

    reg [CNT_WIDTH-1:0] clk_cnt;
    reg [3:0]           bit_idx;
    reg [7:0]           tx_data;
    reg [1:0]           state;

    localparam IDLE  = 2'b00;
    localparam START = 2'b01;
    localparam DATA  = 2'b10;
    localparam STOP  = 2'b11;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state   <= IDLE;
            tx_pin  <= 1'b1;
            tx_busy <= 1'b0;
            tx_done <= 1'b0;
            clk_cnt <= 0;
            bit_idx <= 0;
            tx_data <= 8'h00;
        end else begin
            tx_done <= 1'b0;

            case (state)
                IDLE: begin
                    tx_pin  <= 1'b1;
                    tx_busy <= 1'b0;
                    clk_cnt <= 0;
                    bit_idx <= 0;
                    if (tx_start) begin
                        tx_data <= data_in;
                        tx_busy <= 1'b1;
                        state   <= START;
                    end
                end

                START: begin
                    tx_pin <= 1'b0;
                    if (clk_cnt < BIT_PERIOD - 1) begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end else begin
                        clk_cnt <= 0;
                        state   <= DATA;
                    end
                end

                DATA: begin
                    tx_pin <= tx_data[bit_idx];
                    if (clk_cnt < BIT_PERIOD - 1) begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end else begin
                        clk_cnt <= 0;
                        if (bit_idx < 7) begin
                            bit_idx <= bit_idx + 1'b1;
                        end else begin
                            state <= STOP;
                        end
                    end
                end

                STOP: begin
                    tx_pin <= 1'b1;
                    if (clk_cnt < BIT_PERIOD - 1) begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end else begin
                        tx_done <= 1'b1;
                        tx_busy <= 1'b0;
                        state   <= IDLE;
                    end
                end

                default: state <= IDLE;
            endcase
        end
    end

endmodule
