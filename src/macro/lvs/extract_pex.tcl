# ============================================================
# Standalone Magic extraction of the arbchain hard macro GDS
# into a POST-LAYOUT (PEX) SPICE netlist with parasitic
# capacitance (C-only: no resistors).
#
# Diff vs lvs/extract.tcl (the LVS-grade recipe):
#   - plain `extract` (parasitics ON; the LVS recipe turns them off)
#   - NOT `ext2spice lvs` (lvs mode strips all caps)
#   - cthresh 0.0   : keep every capacitor
#   - rthresh inf   : no resistor elements (C-only PEX)
#   - format ngspice
#   - keeps std cells hierarchical (cell subckts stay black-boxed
#     at their own boundary; device models come from the PDK
#     corner lib at simulation time, as in the smoke test)
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

# C-only PEX output, ngspice syntax
ext2spice cthresh 0.0
ext2spice rthresh infinite
ext2spice format ngspice
ext2spice -o $::env(SAVE_SPICE) $::env(DESIGN_NAME).ext

puts "EXTRACT_PEX_DONE"
