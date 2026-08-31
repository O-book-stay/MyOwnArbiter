`timescale 1ns/1ps
`include "cpu_defines.v"

// ============================================================================
// cpu_core -- 8-bit accumulator machine, multi-cycle, custom tiny ISA
//
// Registers: A, B, PC (8-bit, wraps) and flags Z / C.
// Every instruction is one opcode byte optionally followed by one operand
// byte (see cpu_defines.v for the encoding).
//
// The core talks to the world through one simple byte-wide bus:
//   * present bus_addr with bus_read=1  -> bus_rdata valid one cycle later
//   * present bus_addr/bus_wdata with bus_write=1 (exactly one cycle)
// cpu_top routes this bus to the program RAM and the MMIO registers.
//
// Cycle budget (at 48 MHz): fetch 2 cycles, +1 for instructions with an
// operand, +1 execute, +1 per extra memory beat.  Simplicity beats speed.
// ============================================================================
module cpu_core (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       start,       // 1-cycle pulse from boot FSM: run from 0
    output reg        halted,      // 1 after reset or after HALT instruction

    output reg  [7:0] bus_addr,
    output reg        bus_read,
    output reg        bus_write,
    output reg  [7:0] bus_wdata,
    input  wire [7:0] bus_rdata    // valid while bus_read is high
);

    // ------------------------------------------------------------------
    // States
    // ------------------------------------------------------------------
    localparam [3:0] ST_HALT     = 4'd0;  // parked (reset / HALT / before run)
    localparam [3:0] ST_F0       = 4'd1;  // present PC for opcode fetch
    localparam [3:0] ST_FETCH    = 4'd2;  // latch opcode
    localparam [3:0] ST_FETCH_OP = 4'd3;  // latch operand (prefetched)
    localparam [3:0] ST_EXEC     = 4'd4;  // decode + execute / start bus beat
    localparam [3:0] ST_MEMRD    = 4'd5;  // complete read-based instructions
    localparam [3:0] ST_WRITE    = 4'd6;  // write beat (STD / OUTI / INC)
    localparam [3:0] ST_NEXT     = 4'd7;  // present PC for the next fetch

    reg [3:0] state;
    reg [7:0] ir;                       // instruction register
    reg [7:0] operand;
    reg [7:0] pc;
    reg [7:0] reg_a, reg_b;
    reg       flag_z, flag_c;

    // Opcode currently being decoded: during ST_FETCH the incoming opcode
    // is still on bus_rdata (ir latches at the end of the cycle).
    wire [7:0] dec_op = (state == ST_FETCH) ? bus_rdata : ir;

    reg needs_op;
    always @* begin
        case (dec_op)
            `OP_LDI, `OP_LDD, `OP_STD,
            `OP_ADDI, `OP_ADDM, `OP_SUBI, `OP_SUBM,
            `OP_ANDI, `OP_ORI, `OP_XORI,
            `OP_JMP, `OP_JZ, `OP_JNZ, `OP_JC,
            `OP_INC, `OP_OUTI: needs_op = 1'b1;
            default:           needs_op = 1'b0;   // NOP, MOV*, HALT
        endcase
    end

    // ------------------------------------------------------------------
    // ALU results (combinational, synthesis prunes the unused ones)
    //   9-bit results: bit 8 = carry-out (add/inc) or borrow (sub)
    // ------------------------------------------------------------------
    wire [8:0] addi_res = {1'b0, reg_a} + {1'b0, operand};
    wire [8:0] subi_res = {1'b0, reg_a} - {1'b0, operand};
    wire [7:0] andi_res = reg_a & operand;
    wire [7:0] ori_res  = reg_a | operand;
    wire [7:0] xori_res = reg_a ^ operand;

    wire [8:0] addm_res = {1'b0, reg_a} + {1'b0, bus_rdata};
    wire [8:0] subm_res = {1'b0, reg_a} - {1'b0, bus_rdata};
    wire [8:0] inc_res  = {1'b0, bus_rdata} + 9'd1;

    // ------------------------------------------------------------------
    // Main FSM
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= ST_HALT;
            halted    <= 1'b1;
            ir        <= 8'h00;
            operand   <= 8'h00;
            pc        <= 8'h00;
            reg_a     <= 8'h00;
            reg_b     <= 8'h00;
            flag_z    <= 1'b0;
            flag_c    <= 1'b0;
            bus_addr  <= 8'h00;
            bus_read  <= 1'b0;
            bus_write <= 1'b0;
            bus_wdata <= 8'h00;
        end else begin
            case (state)

                // Parked until the boot FSM issues a run command.
                ST_HALT: begin
                    bus_read  <= 1'b0;
                    bus_write <= 1'b0;
                    if (start) begin
                        pc     <= 8'h00;
                        halted <= 1'b0;
                        state  <= ST_F0;
                    end
                end

                // Present PC; data arrives next cycle in ST_FETCH.
                ST_F0: begin
                    bus_addr <= pc;
                    bus_read <= 1'b1;
                    state    <= ST_FETCH;
                end

                // Opcode is on bus_rdata now.  If the instruction takes an
                // operand, keep the bus busy and prefetch it (PC+1).
                ST_FETCH: begin
                    ir <= dec_op;
                    if (needs_op) begin
                        bus_addr <= pc + 8'd1;
                        bus_read <= 1'b1;
                        pc       <= pc + 8'd2;
                        state    <= ST_FETCH_OP;
                    end else begin
                        bus_read <= 1'b0;
                        pc       <= pc + 8'd1;
                        state    <= ST_EXEC;
                    end
                end

                // Operand is on bus_rdata now.
                ST_FETCH_OP: begin
                    operand  <= bus_rdata;
                    bus_read <= 1'b0;
                    state    <= ST_EXEC;
                end

                // Execute.  Single-beat instructions finish here; memory
                // instructions start their bus beat and complete in
                // ST_MEMRD / ST_WRITE.
                ST_EXEC: begin
                    case (ir)
                        `OP_NOP: state <= ST_NEXT;

                        `OP_LDI: begin
                            reg_a  <= operand;
                            flag_z <= (operand == 8'h00);
                            state  <= ST_NEXT;
                        end

                        `OP_MOV_BA: begin
                            reg_b <= reg_a;
                            state <= ST_NEXT;
                        end
                        `OP_MOV_AB: begin
                            reg_a <= reg_b;
                            state <= ST_NEXT;
                        end

                        // Memory-read instructions: start the read beat;
                        // they complete in ST_MEMRD.
                        `OP_LDD, `OP_ADDM, `OP_SUBM, `OP_INC: begin
                            bus_addr <= operand;
                            bus_read <= 1'b1;
                            state    <= ST_MEMRD;
                        end

                        `OP_STD: begin
                            bus_addr  <= operand;
                            bus_wdata <= reg_a;
                            bus_write <= 1'b1;
                            state     <= ST_WRITE;
                        end

                        `OP_ADDI: begin
                            reg_a  <= addi_res[7:0];
                            flag_c <= addi_res[8];
                            flag_z <= (addi_res[7:0] == 8'h00);
                            state  <= ST_NEXT;
                        end
                        `OP_SUBI: begin
                            reg_a  <= subi_res[7:0];
                            flag_c <= ~subi_res[8];      // C=1 when no borrow
                            flag_z <= (subi_res[7:0] == 8'h00);
                            state  <= ST_NEXT;
                        end
                        `OP_ANDI: begin
                            reg_a  <= andi_res;
                            flag_c <= 1'b0;
                            flag_z <= (andi_res == 8'h00);
                            state  <= ST_NEXT;
                        end
                        `OP_ORI: begin
                            reg_a  <= ori_res;
                            flag_c <= 1'b0;
                            flag_z <= (ori_res == 8'h00);
                            state  <= ST_NEXT;
                        end
                        `OP_XORI: begin
                            reg_a  <= xori_res;
                            flag_c <= 1'b0;
                            flag_z <= (xori_res == 8'h00);
                            state  <= ST_NEXT;
                        end

                        `OP_JMP: begin
                            pc    <= operand;
                            state <= ST_NEXT;
                        end
                        `OP_JZ: begin
                            if (flag_z) pc <= operand;
                            state <= ST_NEXT;
                        end
                        `OP_JNZ: begin
                            if (!flag_z) pc <= operand;
                            state <= ST_NEXT;
                        end
                        `OP_JC: begin
                            if (flag_c) pc <= operand;
                            state <= ST_NEXT;
                        end

                        `OP_OUTI: begin
                            bus_addr  <= `ADDR_GPIO;
                            bus_wdata <= operand;
                            bus_write <= 1'b1;
                            state     <= ST_WRITE;
                        end

                        `OP_HALT: begin
                            halted <= 1'b1;
                            state  <= ST_HALT;
                        end

                        default: state <= ST_NEXT;  // unknown = NOP
                    endcase
                end

                // Read data (mem[operand]) is on bus_rdata now.
                ST_MEMRD: begin
                    bus_read <= 1'b0;
                    case (ir)
                        `OP_LDD: begin
                            reg_a  <= bus_rdata;
                            flag_z <= (bus_rdata == 8'h00);
                            state  <= ST_NEXT;
                        end
                        `OP_ADDM: begin
                            reg_a  <= addm_res[7:0];
                            flag_c <= addm_res[8];
                            flag_z <= (addm_res[7:0] == 8'h00);
                            state  <= ST_NEXT;
                        end
                        `OP_SUBM: begin
                            reg_a  <= subm_res[7:0];
                            flag_c <= ~subm_res[8];      // C=1 when no borrow
                            flag_z <= (subm_res[7:0] == 8'h00);
                            state  <= ST_NEXT;
                        end
                        // INC: write the incremented value straight back.
                        `OP_INC: begin
                            flag_z    <= (inc_res[7:0] == 8'h00);
                            flag_c    <= inc_res[8];
                            bus_wdata <= inc_res[7:0];
                            bus_write <= 1'b1;           // bus_addr still operand
                            state     <= ST_WRITE;
                        end
                        default: state <= ST_NEXT;
                    endcase
                end

                // One-cycle write beat is active in this state.
                ST_WRITE: begin
                    bus_write <= 1'b0;
                    state     <= ST_NEXT;
                end

                // Present PC for the next instruction fetch.
                ST_NEXT: begin
                    bus_addr <= pc;
                    bus_read <= 1'b1;
                    state    <= ST_FETCH;
                end

                default: state <= ST_HALT;
            endcase
        end
    end

endmodule
