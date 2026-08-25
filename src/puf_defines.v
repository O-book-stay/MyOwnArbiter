`ifndef PUF_DEFINES_V
`define PUF_DEFINES_V

`ifndef RESP_BITS
`define RESP_BITS       16          // challenge bus width AND response bits
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
// ARB_STAGES is the number of switch stages in the arbiter chain.
// It must match the symmetric hard macro `arbchain` (src/macro).
`ifndef ARB_STAGES
`define ARB_STAGES      16          // switch stages in the arbiter chain
`endif

`ifndef ARB_SETTLE_CYCLES
`define ARB_SETTLE_CYCLES 64        // launch / settle window per race
`endif

`ifndef BOOT_K
`define BOOT_K          8           // bootstrap rounds -> hidden[7:0]
`endif

`ifndef VOTE
`define VOTE            3           // majority-vote depth per response bit
`endif

`endif
