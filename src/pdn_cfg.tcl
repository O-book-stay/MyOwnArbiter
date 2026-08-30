# =====================================================================
#  pdn_cfg.tcl — tt_um_obookstay_puf  (修复 PDN-0232/0233)
#
#  核心修复：
#   1. core grid strap 强制 -extend_to_boundary，确保覆盖 macro
#   2. macro grid 自带 met4/met5 strap，避免 InstanceGrid 报空
#   3. macro 内部 met4 strap 连接 pin，再 via4 连 met5，再与 core met5 同层合并
# =====================================================================

source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
source $::env(SCRIPTS_DIR)/openroad/common/set_global_connections.tcl
set_global_connections

# ==========================================================
#  1. Macro PG 逻辑连接（必须先于 grid 定义）
# ==========================================================
add_global_connection -net $::env(VDD_NET) \
    -inst_pattern {u_puf_top\.u_chain} -pin_pattern {^VPWR$} -power
add_global_connection -net $::env(GND_NET) \
    -inst_pattern {u_puf_top\.u_chain} -pin_pattern {^VGND$} -ground
global_connect

# ==========================================================
#  2. Secondary power nets
# ==========================================================
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

# ==========================================================
#  3. Core Grid
# ==========================================================
if { $::env(PDN_MULTILAYER) == 1 } {

    set arg_list [list]
    if { $::env(PDN_ENABLE_PINS) } {
        lappend arg_list -pins "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"
    }

    define_pdn_grid \
        -name stdcell_grid \
        -starts_with POWER \
        -voltage_domain CORE \
        {*}$arg_list

    # ---- met4 vertical straps（强制 extend_to_boundary 覆盖 macro）----
    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_VERTICAL_LAYER) \
        -width $::env(PDN_VWIDTH) \
        -pitch $::env(PDN_VPITCH) \
        -offset $::env(PDN_VOFFSET) \
        -spacing $::env(PDN_VSPACING) \
        -starts_with POWER \
        -extend_to_boundary

    # ---- met5 horizontal straps（强制 extend_to_boundary 覆盖 macro）----
    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_HORIZONTAL_LAYER) \
        -width $::env(PDN_HWIDTH) \
        -pitch $::env(PDN_HPITCH) \
        -offset $::env(PDN_HOFFSET) \
        -spacing $::env(PDN_HSPACING) \
        -starts_with POWER \
        -extend_to_boundary

    # ---- core: met4 ↔ met5 ----
    add_pdn_connect \
        -grid stdcell_grid \
        -layers "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"

} else {

    set arg_list [list]
    if { $::env(PDN_ENABLE_PINS) } {
        lappend arg_list -pins "$::env(PDN_VERTICAL_LAYER)"
    }

    define_pdn_grid \
        -name stdcell_grid \
        -starts_with POWER \
        -voltage_domain CORE \
        {*}$arg_list

    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_VERTICAL_LAYER) \
        -width $::env(PDN_VWIDTH) \
        -pitch $::env(PDN_VPITCH) \
        -offset $::env(PDN_VOFFSET) \
        -spacing $::env(PDN_VSPACING) \
        -starts_with POWER \
        -extend_to_boundary
}

# ==========================================================
#  4. Standard-cell followpin rails
# ==========================================================
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

# ==========================================================
#  5. Core ring（可选，保持原样）
# ==========================================================
if { $::env(PDN_CORE_RING) == 1 } {
    if { $::env(PDN_MULTILAYER) == 1 } {
        set arg_list [list]
        append_if_flag   arg_list PDN_CORE_RING_ALLOW_OUT_OF_DIE -allow_out_of_die
        append_if_flag   arg_list PDN_CORE_RING_CONNECT_TO_PADS  -connect_to_pads
        append_if_equals arg_list PDN_EXTEND_TO "boundary"       -extend_to_boundary

        set pdn_core_vertical_layer   $::env(PDN_VERTICAL_LAYER)
        set pdn_core_horizontal_layer $::env(PDN_HORIZONTAL_LAYER)

        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] } {
            set pdn_core_vertical_layer $::env(PDN_CORE_VERTICAL_LAYER)
        }
        if { [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } {
            set pdn_core_horizontal_layer $::env(PDN_CORE_HORIZONTAL_LAYER)
        }

        add_pdn_ring \
            -grid stdcell_grid \
            -layers  "$pdn_core_vertical_layer $pdn_core_horizontal_layer" \
            -widths  "$::env(PDN_CORE_RING_VWIDTH) $::env(PDN_CORE_RING_HWIDTH)" \
            -spacings "$::env(PDN_CORE_RING_VSPACING) $::env(PDN_CORE_RING_HSPACING)" \
            -core_offset "$::env(PDN_CORE_RING_VOFFSET) $::env(PDN_CORE_RING_HOFFSET)" \
            {*}$arg_list

        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] } {
            add_pdn_connect -grid stdcell_grid \
                -layers "$::env(PDN_CORE_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"
        }
        if { [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } {
            add_pdn_connect -grid stdcell_grid \
                -layers "$::env(PDN_CORE_HORIZONTAL_LAYER) $::env(PDN_VERTICAL_LAYER)"
        }
        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] \
          && [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } {
            add_pdn_connect -grid stdcell_grid \
                -layers "$::env(PDN_CORE_VERTICAL_LAYER) $::env(PDN_CORE_HORIZONTAL_LAYER)"
        }
    } else {
        throw APPLICATION "PDN_CORE_RING cannot be used when PDN_MULTILAYER is set to false."
    }
}

# ==========================================================
#  6. ★ Macro Grid — arbchain 电源连接（关键修复区）
# ==========================================================
#  原理：
#   - InstanceGrid 必须自带 strap，否则 PDN-0232/0233
#   - macro 内部 met4 strap 连接 VPWR/VGND pin
#   - macro 内部 met5 strap via4 连接 met4 strap
#   - macro 内部 met5 strap 与 core met5 strap 同层重叠自动合并
# ==========================================================
if { $::env(PDN_MULTILAYER) == 1 } {

    define_pdn_grid -macro \
        -name arbchain_pdn \
        -instances {u_puf_top.u_chain} \
        -orient {R0 R90 R180 R270 MX MY MXR90 MYR90} \
        -grid_over_pg_pins \
        -starts_with POWER \
        -halo {0 0}

    # macro 内部 met4 strap（连接 pin）
    add_pdn_stripe -grid arbchain_pdn \
        -layer $::env(PDN_VERTICAL_LAYER) \
        -width 2.0 -pitch 10.0 -offset 0.0 -starts_with POWER

    # macro 内部 met5 strap（连接 met4 strap，并延伸至与 core met5 重叠）
    add_pdn_stripe -grid arbchain_pdn \
        -layer $::env(PDN_HORIZONTAL_LAYER) \
        -width 2.0 -pitch 10.0 -offset 0.0 -starts_with POWER

    # macro 内部 met4 ↔ met5 互连
    add_pdn_connect -grid arbchain_pdn \
        -layers "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"
}