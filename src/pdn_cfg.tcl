# =====================================================================
#  pdn_cfg.tcl — tt_um_obookstay_puf  (met4-only, geometry-driven)
#
#  TT precheck forbids met5 entirely on sky130A (tt/precheck/tech_data.py:
#  forbidden_layers = met5.drawing/pin/label; power pins must be met4),
#  so this PDN is met4-only: vertical met4 straps + met1 followpins.
#
#  The arbchain macro exposes VPWR/VGND as full-width met4 stripes
#  (arbchain.lef), so a strap overlapping them connects by same-layer
#  abutment — no vias, no met5.
#
#  The "targeted" strap pair is placed by reading the macro's actual
#  ITerm bboxes from odb, so it survives re-placement / re-orientation
#  as long as the PG pins stay on met4.  Distribution straps are kept
#  >= 0.3 um (met4 spacing) clear of the targeted pair.
#
#  Verification: after harden, run check_pdn_def.py against the final
#  DEF (asserts strap positions/nets and zero met5).
# =====================================================================

source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
source $::env(SCRIPTS_DIR)/openroad/common/set_global_connections.tcl
set_global_connections

# ---- secondary power nets (stock boilerplate) -----------------------
set secondary []
foreach vdd $::env(VDD_NETS) gnd $::env(GND_NETS) {
    if { $vdd != $::env(VDD_NET)} {
        lappend secondary $vdd
        set db_net [[ord::get_db_block] findNet $vdd]
        if {$db_net == "NULL"} {
            set net [odb::dbNet_create [ord::get_db_block] $vdd]
            $net setSpecial
            $net setSigType "POWER"
        }
    }
    if { $gnd != $::env(GND_NET)} {
        lappend secondary $gnd
        set db_net [[ord::get_db_block] findNet $gnd]
        if {$db_net == "NULL"} {
            set net [odb::dbNet_create [ord::get_db_block] $gnd]
            $net setSpecial
            $net setSigType "GROUND"
        }
    }
}

set_voltage_domain -name CORE -power $::env(VDD_NET) -ground $::env(GND_NET) \
    -secondary_power $secondary

# ---- safety: this script implements the met4-only TT topology -------
if { $::env(PDN_MULTILAYER) == 1 } {
    throw APPLICATION "pdn_cfg.tcl: set FP_PDN_MULTILAYER to 0 — met5 is forbidden by the TT precheck"
}
if { $::env(PDN_VERTICAL_LAYER) != "met4" } {
    throw APPLICATION "pdn_cfg.tcl: expected PDN_VERTICAL_LAYER=met4, got '$::env(PDN_VERTICAL_LAYER)'"
}

# ---- read macro PG pin bboxes (die coords, um) ----------------------
set block [ord::get_db_block]
set core  [$block getCoreArea]
set core_llx [ord::dbu_to_microns [$core xMin]]
set core_urx [ord::dbu_to_microns [$core xMax]]

proc pg_pin_bbox { inst_name pin_name } {
    set inst [[ord::get_db_block] findInst $inst_name]
    if { $inst == "NULL" } {
        throw APPLICATION "pdn_cfg.tcl: instance $inst_name not found"
    }
    set iterm [$inst findITerm $pin_name]
    if { $iterm == "NULL" } {
        throw APPLICATION "pdn_cfg.tcl: pin $pin_name not found on $inst_name"
    }
    set bbox [$iterm getBBox]
    return [list \
        [ord::dbu_to_microns [$bbox xMin]] \
        [ord::dbu_to_microns [$bbox yMin]] \
        [ord::dbu_to_microns [$bbox xMax]] \
        [ord::dbu_to_microns [$bbox yMax]]]
}

lassign [pg_pin_bbox u_puf_top.u_chain VPWR] v_llx v_lly v_urx v_ury
lassign [pg_pin_bbox u_puf_top.u_chain VGND] g_llx g_lly g_urx g_ury
puts "pdn_cfg: VPWR pin bbox (um): $v_llx $v_lly $v_urx $v_ury"
puts "pdn_cfg: VGND pin bbox (um): $g_llx $g_lly $g_urx $g_ury"
puts "pdn_cfg: core area x: $core_llx .. $core_urx"

set w_pin [expr {$v_urx - $v_llx}]
set gap   [expr {$g_llx - $v_urx}]
if { $w_pin <= 0 || abs(($g_urx - $g_llx) - $w_pin) > 0.01 } {
    throw APPLICATION "pdn_cfg.tcl: VPWR/VGND pin bands are not equal-width met4 stripes ([expr {$v_urx - $v_llx}] vs [expr {$g_urx - $g_llx}])"
}
if { $gap < 0.3 } {
    throw APPLICATION "pdn_cfg.tcl: VPWR/VGND pin bands too close together (gap $gap um)"
}

# ---- obstruction bloat of the pins ----------------------------------
#  pdngen turns every macro PG pin into a same-layer obstruction
#  bloated by the layer's min spacing (Shape::generateObstruction) and
#  cuts straps away from it.  The ONLY way a met4 strap survives over
#  its own pin is Shape::cut's same-net exemption, which requires the
#  strap to fully span the bloated pin rect across its width axis.
#  So each targeted strap is wider than the pin by 2 * bloat.
set bloat 0.4
if { ![catch {
    set met4 [[$block getTech] findLayer met4]
    $met4 getSpacing [expr {round($w_pin * 1000)}] 0
} sp_dbu] } {
    if { $sp_dbu > 0 } {
        set bloat [expr {$sp_dbu / 1000.0 + 0.1}]
    }
}
puts "pdn_cfg: met4 pin obstruction bloat: $bloat um"
set w_t [expr {$w_pin + 2.0 * $bloat}]                       ;# targeted strap width
set sp_t [expr {($g_llx - $bloat) - ($v_urx + $bloat)}]      ;# P-to-G edge gap
if { $sp_t < 0.3 } {
    throw APPLICATION "pdn_cfg.tcl: targeted straps would violate met4 spacing ($sp_t um)"
}

set w_reg  $::env(PDN_VWIDTH)
set sp_reg $::env(PDN_VSPACING)
set pitch  $::env(PDN_VPITCH)

# ---------------------------------------------------------------------
#  Core grid: met4 vertical straps only; tile power pins on met4
# ---------------------------------------------------------------------
set arg_list [list]
if { $::env(PDN_ENABLE_PINS) } {
    lappend arg_list -pins $::env(PDN_VERTICAL_LAYER)
}

define_pdn_grid \
    -name stdcell_grid \
    -starts_with POWER \
    -voltage_domain CORE \
    {*}$arg_list

# ---- (1) targeted pair right on the macro PG pin bands --------------
#  pdngen strap-pair model (Straps::makeStraps): the offset is the
#  CENTER of the first strap; the second net's strap starts at
#  center + width + spacing; pitch/number_of_straps count P/G pairs.
#  One pair: P covers the bloated VPWR band, G the bloated VGND band.
#  Width = pin + 2*bloat so Shape::cut's same-net exemption fires and
#  the strap actually lands on the pin.  Asserted post-run by
#  check_pdn_def.py.
add_pdn_stripe \
    -grid stdcell_grid \
    -layer $::env(PDN_VERTICAL_LAYER) \
    -width $w_t \
    -spacing $sp_t \
    -pitch 1000.0 \
    -offset [expr {($v_llx + $v_urx) / 2.0 - $core_llx}] \
    -starts_with POWER \
    -number_of_straps 1

# ---- (2) west distribution straps -----------------------------------
#  Keep every strap edge >= bloat + 0.3 um clear of the targeted pair
#  and of every met4 signal pin of the macro (e.g. "launch": a strap
#  sitting on top of a pin's x-window traps the pin's access wire).
#  Pairs: P at off, G at off + width + spacing (left edges).
set off_w $::env(PDN_VOFFSET)
set clear_lo [expr {$v_llx - $bloat - 0.3 - $w_reg}]
set n_west [expr {int(floor(($clear_lo - ($core_llx + $off_w + 2.0 * $w_reg + $sp_reg)) / double($pitch))) + 1}]
if { $n_west < 1 } { set n_west 1 }
puts "pdn_cfg: west straps: $n_west pair(s) from core-relative offset $off_w"
add_pdn_stripe \
    -grid stdcell_grid \
    -layer $::env(PDN_VERTICAL_LAYER) \
    -width $w_reg \
    -pitch $pitch \
    -offset $off_w \
    -spacing $sp_reg \
    -starts_with POWER \
    -number_of_straps $n_west

# ---- (3) east distribution straps (fill to the boundary) ------------
#  Straps may NOT cross the macro: any strap cut by the macro's met4
#  OBS leaves partial rectangles, and the TT pin check requires EVERY
#  power port rect to touch both the bottom and the top die edges
#  (tt/precheck/pin_check.py).  So the east fill starts behind the
#  macro's east edge instead.
set inst2 [$block findInst u_puf_top.u_chain]
set macro_urx [ord::dbu_to_microns [[$inst2 getBBox] xMax]]
set off_e [expr {($macro_urx + $bloat + 0.3 + $w_reg / 2.0) - $core_llx}]
puts "pdn_cfg: east straps from core-relative offset $off_e (first strap x = [expr {$off_e + $core_llx - $w_reg/2.0}])"
add_pdn_stripe \
    -grid stdcell_grid \
    -layer $::env(PDN_VERTICAL_LAYER) \
    -width $w_reg \
    -pitch $pitch \
    -offset $off_e \
    -spacing $sp_reg \
    -starts_with POWER

# ---- met1 followpin rails + via stack met1->met4 --------------------
if { $::env(PDN_ENABLE_RAILS) == 1 } {
    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_RAIL_LAYER) \
        -width $::env(PDN_RAIL_WIDTH) \
        -followpins

    add_pdn_connect \
        -grid stdcell_grid \
        -layers "$::env(PDN_RAIL_LAYER) $::env(PDN_VERTICAL_LAYER)"
}

# ---------------------------------------------------------------------
#  NO InstanceGrid for the macro.  Any instance grid turns the macro's
#  own met4 PG pins into net-less obstructions that cut met4 straps
#  (pdngen has no same-layer strap-to-pin contact path at all).
#  Without an instance grid, the macro's pins enter the core grid's
#  obstruction set WITH their nets, and the same-net exemption in
#  Shape::cut keeps the targeted straps alive over the pins.
# ---------------------------------------------------------------------
