`timescale 1ns/1ps
`include "cpu_defines.v"

// ============================================================================
// cpu_top -- program RAM + memory-mapped IO + UART boot loader around cpu_core
//
// Memory map:
//   0x00-0x1F  program/data RAM (`RAM_DEPTH bytes, flop based)
//   0xFC       GPIO output register      (drives uio[7:0])
//   0xFD       read ui[7:0] pins
//   0xFE       UART data     (write = transmit, read = last RX byte)
//   0xFF       UART status   (bit0 = TX busy, bit1 = RX available)
//   other      reads 0, writes ignored
//
// Boot protocol on the UART (host -> chip, 115200 8N1):
//   'L' + len(1B) + len program bytes   load RAM from 0x00
//   'R'                                 run from PC = 0
// Loading/running is only accepted while the core is halted.
//
// LEDs: R = boot/loading, G = running, B = halted.
// ============================================================================
module cpu_top (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       uart_rx_pin,
    output wire       uart_tx_pin,
    output wire       led_r,
    output wire       led_g,
    output wire       led_b,
    input  wire [7:0] ui_pins,     // dedicated inputs, readable via MMIO
    output wire [7:0] gpio_out     // GPIO register, driven onto uio[7:0]
);

    // ------------------------------------------------------------------
    // CPU core
    // ------------------------------------------------------------------
    wire [7:0] bus_addr, bus_wdata, bus_rdata;
    wire       bus_read, bus_write;
    wire       cpu_halted, cpu_start;

    cpu_core u_core (
        .clk       (clk),
        .rst_n     (rst_n),
        .start     (cpu_start),
        .halted    (cpu_halted),
        .bus_addr  (bus_addr),
        .bus_read  (bus_read),
        .bus_write (bus_write),
        .bus_wdata (bus_wdata),
        .bus_rdata (bus_rdata)
    );

    // ------------------------------------------------------------------
    // UART
    // ------------------------------------------------------------------
    wire [7:0] rx_data;
    wire       rx_valid;
    wire       tx_busy;
    wire       tx_done;

    wire tx_start = bus_write && (bus_addr == `ADDR_UART_DATA) && !tx_busy;

    uart_tx u_uart_tx (
        .clk      (clk),
        .rst_n    (rst_n),
        .tx_start (tx_start),
        .data_in  (bus_wdata),
        .tx_pin   (uart_tx_pin),
        .tx_busy  (tx_busy),
        .tx_done  (tx_done)
    );

    uart_rx u_uart_rx (
        .clk      (clk),
        .rst_n    (rst_n),
        .rx_pin   (uart_rx_pin),
        .rx_data  (rx_data),
        .rx_valid (rx_valid)
    );

    // ------------------------------------------------------------------
    // Boot loader FSM
    // ------------------------------------------------------------------
    localparam [1:0] B_WAIT = 2'd0;
    localparam [1:0] B_LEN  = 2'd1;
    localparam [1:0] B_DATA = 2'd2;

    reg [1:0]        b_state;
    reg [7:0]        b_len;
    reg [`RAM_AW-1:0] b_idx;
    reg              started;   // 1 once a 'R' was accepted

    wire boot_idle = (b_state == B_WAIT) && (!started || cpu_halted);
    wire is_load   = rx_valid && boot_idle && (rx_data == `BOOT_LOAD);
    wire is_run    = rx_valid && boot_idle && (rx_data == `BOOT_RUN);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            b_state <= B_WAIT;
            b_len   <= 8'h00;
            b_idx   <= {`RAM_AW{1'b0}};
            started <= 1'b0;
        end else begin
            case (b_state)
                B_WAIT: begin
                    if (is_load)
                        b_state <= B_LEN;
                    else if (is_run)
                        started <= 1'b1;    // b_state stays B_WAIT
                end
                B_LEN: begin
                    if (rx_valid) begin
                        b_len   <= rx_data;
                        b_idx   <= {`RAM_AW{1'b0}};
                        b_state <= B_DATA;
                    end
                end
                B_DATA: begin
                    if (rx_valid) begin
                        b_idx <= b_idx + 1'b1;
                        if (b_idx == b_len - 1'b1)
                            b_state <= B_WAIT;   // image complete
                    end
                end
                default: b_state <= B_WAIT;
            endcase
        end
    end

    assign cpu_start = is_run;

    // ------------------------------------------------------------------
    // Program/data RAM
    //   * boot loader writes during B_DATA
    //   * CPU writes while running (addresses 0x00-0x1F)
    //   * contents are NOT initialised: programs must store before load
    // ------------------------------------------------------------------
    reg [7:0] ram [0:`RAM_DEPTH-1];

    wire boot_we  = (b_state == B_DATA) && rx_valid;
    wire cpu_we   = bus_write && (bus_addr[7:5] == 3'b000);  // 0x00-0x1F

    always @(posedge clk) begin
        if (boot_we)
            ram[b_idx] <= rx_data;
        else if (cpu_we)
            ram[bus_addr[`RAM_AW-1:0]] <= bus_wdata;
    end

    // ------------------------------------------------------------------
    // MMIO registers
    // ------------------------------------------------------------------
    reg [7:0] gpio_reg;
    reg       rx_avail;

    wire rx_read = bus_read && (bus_addr == `ADDR_UART_DATA);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            gpio_reg <= 8'h00;
            rx_avail <= 1'b0;
        end else begin
            if (bus_write && (bus_addr == `ADDR_GPIO))
                gpio_reg <= bus_wdata;

            if (rx_read)
                rx_avail <= 1'b0;
            else if (rx_valid && started)   // RX for the program, not boot
                rx_avail <= 1'b1;
        end
    end

    assign gpio_out = gpio_reg;

    // ------------------------------------------------------------------
    // Bus read mux (combinational on the registered bus signals)
    // ------------------------------------------------------------------
    reg [7:0] rdata_mux;
    always @* begin
        if (bus_addr[7:5] == 3'b000)                       // 0x00-0x1F: RAM
            rdata_mux = ram[bus_addr[`RAM_AW-1:0]];
        else if (bus_addr == `ADDR_GPIO)
            rdata_mux = gpio_reg;
        else if (bus_addr == `ADDR_PINS)
            rdata_mux = ui_pins;
        else if (bus_addr == `ADDR_UART_DATA)
            rdata_mux = rx_data;
        else if (bus_addr == `ADDR_UART_STAT)
            rdata_mux = {6'b000000, rx_avail, tx_busy};
        else
            rdata_mux = 8'h00;
    end

    assign bus_rdata = bus_read ? rdata_mux : 8'h00;

    // ------------------------------------------------------------------
    // Status LEDs
    // ------------------------------------------------------------------
    assign led_r = ~started;                 // boot / loading
    assign led_g = started && !cpu_halted;   // running
    assign led_b = started && cpu_halted;    // halted

endmodule
