#!/usr/bin/env python3
"""Remove degenerate (zero-area) shapes from a GDS file.

Tiny Tapeout's precheck runs a KLayout zero_area DRC over the final
GDS, and a single zero-length path inside the `arbchain` hard macro
(at 17.13, 74.5 um) fails it:  "Klayout zero_area failed".

A zero-length path carries no geometry (zero area on silicon), so
removing it cannot change the layout, LVS result or netlist.

Usage:
    python remove_degenerate.py [--check] [file.gds ...]

Without arguments the script cleans arbchain.gds next to itself (the
file the build embeds, see src/config.json MACROS.arbchain.gds).
--check only reports what would be removed.  The original file is
kept as <name>.gds.bak before an in-place fix.
"""

import os
import shutil
import sys

try:
    import pya
except ImportError:  # pip-installed klayout without the pya shim
    import klayout.db as pya


def degenerate_reason(shape, dbu):
    """Return a human-readable reason if the shape is degenerate, else None."""
    if shape.is_path():
        p = shape.path
        pts = [(pt.x, pt.y) for pt in p.each_point()]
        if p.width == 0:
            return "zero-width path (%d pts)" % len(pts)
        if len(set(pts)) <= 1:
            x_um, y_um = pts[0][0] * dbu, pts[0][1] * dbu
            return "zero-length path at (%g, %g) um (%d identical pts)" % (
                x_um, y_um, len(pts))
    elif shape.is_polygon():
        if shape.polygon.area() == 0:
            return "zero-area polygon"
    elif shape.is_simple_polygon():
        if shape.simple_polygon.area() == 0:
            return "zero-area simple polygon"
    elif shape.is_box():
        b = shape.box
        if b.width() == 0 or b.height() == 0:
            return "zero-area box (%s)" % b.to_s()
    return None


def find_degenerate(layout):
    """Collect (cell, layer_info, shape, reason) for all degenerate shapes."""
    found = []
    for cell in layout.each_cell():
        for li in layout.layer_indexes():
            shapes = cell.shapes(li)
            if shapes.size() == 0:
                continue
            info = layout.get_info(li).to_s()
            for shape in shapes.each():
                why = degenerate_reason(shape, layout.dbu)
                if why:
                    found.append((cell, li, shape, info, why))
    return found


def describe(layout, item):
    cell, li, shape, info, why = item
    bb = shape.bbox()
    box_um = (bb.left * layout.dbu, bb.bottom * layout.dbu,
              bb.right * layout.dbu, bb.top * layout.dbu)
    return "cell %-25s layer %-14s %-46s bbox (%g, %g)-(%g, %g) um" % (
        cell.name, info, why, box_um[0], box_um[1], box_um[2], box_um[3])


def geometry_stats(layout):
    """Shape/instance counts per cell, to prove nothing else changed."""
    stats = {}
    for cell in layout.each_cell():
        n_shapes = sum(cell.shapes(li).size() for li in layout.layer_indexes())
        n_insts = sum(1 for _ in cell.each_inst())
        stats[cell.name] = (n_shapes, n_insts)
    return stats


def process(path, check_only):
    print("==== %s" % path)
    layout = pya.Layout()
    layout.read(path)
    found = find_degenerate(layout)

    if not found:
        print("  clean: no degenerate shapes")
        return 0

    for item in found:
        print("  FOUND %s" % describe(layout, item))

    if check_only:
        print("  %d degenerate shape(s) (report only)" % len(found))
        return 1

    before = geometry_stats(layout)
    bak = path + ".bak"
    shutil.copy2(path, bak)
    print("  backup -> %s" % bak)

    for cell, li, shape, _info, _why in found:
        cell.shapes(li).erase(shape)
    layout.write(path)

    # verify: reload and re-scan
    verify = pya.Layout()
    verify.read(path)
    remaining = find_degenerate(verify)
    after = geometry_stats(verify)

    for name in before:
        b_shapes, b_insts = before[name]
        a_shapes, a_insts = after.get(name, (0, 0))
        if (a_shapes, a_insts) != (b_shapes - len([1 for f in found
                                                   if f[0].name == name]),
                                   b_insts):
            print("  ERROR: unexpected change in cell %s" % name)
            return 1

    if remaining:
        for item in remaining:
            print("  STILL THERE %s" % describe(verify, item))
        print("  FAILED: degenerate shapes remain after rewrite")
        return 1

    print("  removed %d degenerate shape(s), verified clean" % len(found))
    return 0


def main(argv):
    args = [a for a in argv[1:] if a != "--check"]
    check_only = "--check" in argv[1:]
    if not args:
        args = [os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "arbchain.gds")]
    rc = 0
    for path in args:
        rc |= process(path, check_only)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
