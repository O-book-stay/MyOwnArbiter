`ifndef PUF_DEFINES_V
`define PUF_DEFINES_V

`ifndef RO_COUNT
`define RO_COUNT        16
`endif

`ifndef RESP_BITS
`define RESP_BITS       128
`endif

`ifndef CNT_WIDTH
`define CNT_WIDTH       16
`endif

`ifndef MEASURE_CYCLES
`define MEASURE_CYCLES  4800        // 100us @ 48MHz per pair
`endif

`ifndef CLK_FREQ
`define CLK_FREQ        48_000_000
`endif

`ifndef BAUD_RATE
`define BAUD_RATE       115200
`endif

`ifndef BIT_PERIOD
`define BIT_PERIOD      (`CLK_FREQ / `BAUD_RATE)
`endif

// ============================================================
// Strong PUF (iterative feedback arbiter) parameters
// ============================================================
`ifndef ARB_STAGES
`define ARB_STAGES      48          // switch stages in the arbiter chain
`endif

`ifndef ARB_SETTLE_CYCLES
`define ARB_SETTLE_CYCLES 64        // launch / settle window per race
`endif

`ifndef BOOT_K
`define BOOT_K          32          // bootstrap rounds -> hidden[31:0]
`endif

`ifndef VOTE
`define VOTE            3           // majority-vote depth per response bit
`endif

// ============================================================
// Silicon power-up entropy bank (hybrid anchor for the arbiter PUF)
// ============================================================
`ifndef SILICON_W
`define SILICON_W       128
`endif

`endif
