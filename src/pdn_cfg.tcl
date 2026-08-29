# =====================================================================
# Custom PDN configuration – arbchain macro power connection
#
# 核心策略（第五版，绕开 pdngen 不给 macro pin 打 via4 的限制）：
#   1. 在 met4（PDN_VERTICAL_LAYER）加两根 custom strap，x 位置恰好
#      与 macro 的 VPWR/VGND met4 pin 重叠 → 同层同网自动 merge。
#   2. 在 met5（PDN_HORIZONTAL_LAYER）加两根 custom strap，y 位置覆盖
#      pin 中心 → 与上述 met4 strap 交叉。
#   3. add_pdn_connect "met4 met5" 让 pdngen 在交叉点打 via4。
#   4. 最终电流路径：macro met4 pin ←same layer merge→ custom met4 strap
#      ←via4→ custom met5 strap ←via4→ regular met4 strap → 汇入主 grid。
#
# 关键修复:
#   [Fix 1] global_connect 使 iterm 逻辑连上 net
#   [Fix 2] offset snap 到 0.005um 制造格点
#   [Fix 5] met4 strap 同层 merge（不依赖 pdngen 给 pin 打 via）
# =====================================================================

source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
source $::env(SCRIPTS_DIR)/openroad/common/set_global_connections.tcl
set_global_connections

# [Fix 1] 显式连接 macro PG iterm
add_global_connection -net $::env(VDD_NET) \
    -inst_pattern {u_puf_top\.u_chain} -pin_pattern {^VPWR$} -power
add_global_connection -net $::env(GND_NET) \
    -inst_pattern {u_puf_top\.u_chain} -pin_pattern {^VGND$} -ground
global_connect

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

    set arg_list [list]
    append_if_equals arg_list PDN_EXTEND_TO "core_ring" -extend_to_core_ring
    append_if_equals arg_list PDN_EXTEND_TO "boundary" -extend_to_boundary

    # ---- 标准 met4 vertical straps ----
    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_VERTICAL_LAYER) \
        -width $::env(PDN_VWIDTH) \
        -pitch $::env(PDN_VPITCH) \
        -offset $::env(PDN_VOFFSET) \
        -spacing $::env(PDN_VSPACING) \
        -starts_with POWER \
        {*}$arg_list

    # ---- 标准 met5 horizontal straps ----
    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_HORIZONTAL_LAYER) \
        -width $::env(PDN_HWIDTH) \
        -pitch $::env(PDN_HPITCH) \
        -offset $::env(PDN_HOFFSET) \
        -spacing $::env(PDN_HSPACING) \
        -starts_with POWER \
        {*}$arg_list

    # =================================================================
    # [Fix 5] Custom straps for arbchain macro PG connection
    #
    # After W orientation at (40, 30):
    #   VPWR met4 pin global bbox: (40.000, 39.580)-(41.400, 42.845)
    #     → strap center x = 40.700, width = 1.4
    #   VGND met4 pin global bbox: (42.350, 30.000)-(44.220, 31.725)
    #     → strap center x = 42.750, width = 0.8
    #       (shifted left to avoid met4 OBS starting at x=43.54)
    #
    # Also add met5 straps at pin Y centers for via4 landing.
    # =================================================================
    set blk  [ord::get_db_block]
    set inst [$blk findInst u_puf_top.u_chain]

    if { $inst != "NULL" } {
        set bb   [$inst getBBox]
        set upm  [[ord::get_db_tech] getDbUnitsPerMicron]
        set mx   [expr {[$bb xMin] / double($upm)}]
        set my   [expr {[$bb yMin] / double($upm)}]

        # Core area origin
        if { [catch {set cx [expr {[[$blk getCoreArea] xMin] / double($upm)}]}] } {
            set cx [expr {[[$blk getDieArea] xMin] / double($upm)}]
        }
        if { [catch {set cy [expr {[[$blk getCoreArea] yMin] / double($upm)}]}] } {
            set cy [expr {[[$blk getDieArea] yMin] / double($upm)}]
        }

        set mfg 0.005

        # --- Custom met4 vertical straps (same-layer merge with pin) ---
        # VPWR: x_center = mx + (78.680 - (77.280+78.680)/2) = mx + 0.700
        set vpwr_x [expr {round(($mx + 0.700 - $cx) / $mfg) * $mfg}]
        # VGND: x_center = mx + (78.680 - (74.460+76.330)/2) = mx + 3.285
        #   shifted left to 42.75 to avoid OBS → offset = mx+2.750
        set vgnd_x [expr {round(($mx + 2.750 - $cx) / $mfg) * $mfg}]

        add_pdn_stripe \
            -grid stdcell_grid \
            -layer $::env(PDN_VERTICAL_LAYER) \
            -width 1.4 \
            -pitch 1000 \
            -spacing 1.4 \
            -number_of_straps 1 \
            -offset $vpwr_x \
            -starts_with POWER

        add_pdn_stripe \
            -grid stdcell_grid \
            -layer $::env(PDN_VERTICAL_LAYER) \
            -width 0.8 \
            -pitch 1000 \
            -spacing 0.8 \
            -number_of_straps 1 \
            -offset $vgnd_x \
            -starts_with GROUND

        # --- Custom met5 horizontal straps (via4 landing above pin) ---
        # VPWR: y_center = my + (9.580+12.845)/2 = my + 11.2125
        set vpwr_y [expr {round(($my + 11.2125 - $cy) / $mfg) * $mfg}]
        # VGND: y_center = my + (0.000+1.725)/2 = my + 0.8625
        set vgnd_y [expr {round(($my + 0.8625 - $cy) / $mfg) * $mfg}]

        add_pdn_stripe \
            -grid stdcell_grid \
            -layer $::env(PDN_HORIZONTAL_LAYER) \
            -width 3.4 \
            -pitch 1000 \
            -spacing 3.4 \
            -number_of_straps 1 \
            -offset $vpwr_y \
            -starts_with POWER

        add_pdn_stripe \
            -grid stdcell_grid \
            -layer $::env(PDN_HORIZONTAL_LAYER) \
            -width 2.0 \
            -pitch 1000 \
            -spacing 2.0 \
            -number_of_straps 1 \
            -offset $vgnd_y \
            -starts_with GROUND
    }

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

    set arg_list [list]
    append_if_equals arg_list PDN_EXTEND_TO "core_ring" -extend_to_core_ring
    append_if_equals arg_list PDN_EXTEND_TO "boundary" -extend_to_boundary

    add_pdn_stripe \
        -grid stdcell_grid \
        -layer $::env(PDN_VERTICAL_LAYER) \
        -width $::env(PDN_VWIDTH) \
        -pitch $::env(PDN_VPITCH) \
        -offset $::env(PDN_VOFFSET) \
        -spacing $::env(PDN_VSPACING) \
        -starts_with POWER \
        {*}$arg_list
}

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

if { $::env(PDN_CORE_RING) == 1 } {
    if { $::env(PDN_MULTILAYER) == 1 } {
        set arg_list [list]
        append_if_flag arg_list PDN_CORE_RING_ALLOW_OUT_OF_DIE -allow_out_of_die
        append_if_flag arg_list PDN_CORE_RING_CONNECT_TO_PADS -connect_to_pads
        append_if_equals arg_list PDN_EXTEND_TO "boundary" -extend_to_boundary

        set pdn_core_vertical_layer $::env(PDN_VERTICAL_LAYER)
        set pdn_core_horizontal_layer $::env(PDN_HORIZONTAL_LAYER)

        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] } {
            set pdn_core_vertical_layer $::env(PDN_CORE_VERTICAL_LAYER)
        }

        if { [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } {
            set pdn_core_horizontal_layer $::env(PDN_CORE_HORIZONTAL_LAYER)
        }

        add_pdn_ring \
            -grid stdcell_grid \
            -layers "$pdn_core_vertical_layer $pdn_core_horizontal_layer" \
            -widths "$::env(PDN_CORE_RING_VWIDTH) $::env(PDN_CORE_RING_HWIDTH)" \
            -spacings "$::env(PDN_CORE_RING_VSPACING) $::env(PDN_CORE_RING_HSPACING)" \
            -core_offset "$::env(PDN_CORE_RING_VOFFSET) $::env(PDN_CORE_RING_HOFFSET)" \
            {*}$arg_list

        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] } {
            add_pdn_connect \
                -grid stdcell_grid \
                -layers "$::env(PDN_CORE_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"
        }

        if { [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } {
            add_pdn_connect \
                -grid stdcell_grid \
                -layers "$::env(PDN_CORE_HORIZONTAL_LAYER) $::env(PDN_VERTICAL_LAYER)"
        }

        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] && [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } {
            add_pdn_connect \
                -grid stdcell_grid \
                -layers "$::env(PDN_CORE_VERTICAL_LAYER) $::env(PDN_CORE_HORIZONTAL_LAYER)"
        }

    } else {
        throw APPLICATION "PDN_CORE_RING cannot be used when PDN_MULTILAYER is set to false."
    }
}