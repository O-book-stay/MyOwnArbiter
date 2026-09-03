# ============================================================
# Standalone Magic extraction of the arbchain hard macro GDS
# into a POST-LAYOUT (PEX) SPICE netlist with parasitic
# resistance and capacitance (full R+C).
#
# Diff vs lvs/extract.tcl (the LVS-grade recipe):
#   - plain `extract` (parasitics ON; the LVS recipe turns them off)
#   - NOT `ext2spice lvs` (lvs mode strips all caps)
#   - `extresist`   : distributed wire R. `extract` alone yields
#                     capacitance only; resistance needs this extra
#                     pass, which patches <cell>.res.ext next to the
#                     .ext files. It needs a valid BOX over the cell
#                     ("box 0 0 <W>um <H>um") and works hierarchically
#                     (on a flattened cell it SEGFAULTS in magic
#                     8.3.623, so do NOT flatten).
#   - `ext2spice extresist on` : incorporate the .res.ext patches
#                     (without this the R data is silently ignored)
#   - cthresh 0.0   : keep every capacitor
#   - rthresh 0     : keep every resistor (segment resistances
#                     accumulate; a per-segment threshold would
#                     short them away)
#   - format ngspice
#
# Output is a FLAT top-level netlist (no .subckt wrappers): every
# wire segment becomes an R, every node gets substrate/coupling C.
# The interface nets keep their label names (ch[i], launch, q,
# arb_rst_n, VPWR, VGND) and are drivable directly from the
# testbench (src/macro/sim/arbchain_postsim.spice).
#
# Env (set by run_pex.sh):
#   CURRENT_GDS   path to src/macro/arbchain.gds
#   DESIGN_NAME   arbchain
#   SAVE_SPICE    output netlist path
#   EXT_DIR       dir for .ext files (created if missing)
# Run with: magic -dnull -noconsole -rcfile sky130A.magicrc extract_pex.tcl
# (no args after the script - magic's $argv is the whole command line)
# ============================================================

drc off
crashbackups disable
locking disable

gds read $::env(CURRENT_GDS)

# annotate stdcell port order from the PDK spice (defined by
# $PDKPATH/libs.tech/magic/sky130A.tcl, sourced by the magicrc)
if { [llength [info procs read_pdk_spice]] } {
    read_pdk_spice
} else {
    puts "\[WARN\] read_pdk_spice not available; continuing without it"
}

load $::env(DESIGN_NAME) -dereference

# magic only auto-ports global names (VPWR/VGND); promote every
# top-level label (ch[i], EN, Q, ...) so the interface matches the LEF
if { [llength [info commands port]] } {
    if { [catch {port makeall} msg] } {
        puts "\[WARN\] port makeall failed: $msg"
    }
} else {
    puts "\[WARN\] no port command in this magic build"
}

file mkdir $::env(EXT_DIR)
cd $::env(EXT_DIR)

# full extraction: substrate caps + coupling caps
extract do local
extract
puts "EXTRACT_DONE"
flush stdout

# distributed resistance pass: patches <cell>.res.ext beside the .ext
# (requires the box to identify the resistor boundary; hierarchical
# only - flattening segfaults extresist in magic 8.3.623)
if { [catch {box 0 0 17.28um 82.0um} bm] } {
    puts "\[WARN\] box failed: $bm"
}
flush stdout
if { [catch {extresist} m] } {
    puts "\[ERROR\] extresist failed: $m"
} else {
    puts "EXTRESIST_OK"
}
flush stdout

# R+C PEX output, ngspice syntax
ext2spice cthresh 0.0
ext2spice rthresh 0
ext2spice extresist on
ext2spice format ngspice
ext2spice -o $::env(SAVE_SPICE) $::env(DESIGN_NAME).ext

puts "EXTRACT_PEX_DONE"
