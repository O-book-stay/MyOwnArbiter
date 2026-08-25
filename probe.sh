#!/bin/bash
cd /home/obooky/myownarbiter || exit 1
echo "=== src/macro ==="
ls -la src/macro/
echo "=== which klayout ==="
which klayout || echo "klayout not on PATH"
echo "=== python3 klayout import ==="
python3 -c "import klayout.db as pya; print('pya OK')" 2>&1 | head -5
echo "=== runs ==="
ls runs/ 2>/dev/null
echo "=== runs/wokwi/final ==="
ls runs/wokwi/final/ 2>/dev/null
echo "=== gds dir ==="
ls runs/wokwi/final/gds/ 2>/dev/null
echo "=== pya alternatives ==="
ls /home/obooky/venvs/openlane/lib/python3*/site-packages/ 2>/dev/null | grep -i klayout | head
