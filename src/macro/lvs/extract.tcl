# ============================================================
# Standalone Magic extraction of the arbchain hard macro GDS
# into an LVS-ready (hierarchical, no parasitics) SPICE netlist.
#
# Mirrors LibreLane's scripts/magic/extract_spice.tcl recipe
# (the proven one from the tile flow), GDS-input variant: the
# macro is the TOP cell here, so it gets a full (non-abstract)
# extraction and the embedded std-cell GDS is extracted too.
#
# Env (set by run_lvs.sh):
#   CURRENT_GDS   path to src/macro/arbchain.gds
#   DESIGN_NAME   arbchain
#   SAVE_SPICE    output netlist path
#   EXT_DIR       dir for .ext files (created if missing)
# Run with: magic -dnull -noconsole -rcfile sky130A.magicrc extract.tcl
# (no args after the script — magic's $argv is the whole command line)
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

extract do local
extract no capacitance
extract no coupling
extract no resistance
extract no adjust
extract

ext2spice lvs
ext2spice -o $::env(SAVE_SPICE) $::env(DESIGN_NAME).ext

puts "EXTRACT_DONE"
