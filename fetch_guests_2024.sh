#!/usr/bin/env bash
# Fetches start-list pages for the three 2024 meets and extracts guest divers.
# Requires: curl, python3 (both standard on macOS/Linux).
#
# Usage:
#   chmod +x fetch_guests_2024.sh
#   ./fetch_guests_2024.sh
#
# Output: guests_2024.csv  (columns: meet,eref,diver)
# Also caches raw HTML under cache_guests_2024/ so re-runs don't re-hit the server.

set -e
CACHE_DIR="cache_guests_2024"
OUT_CSV="guests_2024.csv"
mkdir -p "$CACHE_DIR"

# meet_label|mref|eref  -- one line per event to check
EVENTS=$(cat << 'EVENTS_EOF'
PW Novices 2024|1262|1
PW Novices 2024|1262|2
PW Novices 2024|1262|5
PW Novices 2024|1262|6
Natl Finals 2024|1231|1
Natl Finals 2024|1231|2
Natl Finals 2024|1231|3
Natl Finals 2024|1231|9
Natl Finals 2024|1231|10
Natl Finals 2024|1231|11
SE 2024|1222|6
SE 2024|1222|7
SE 2024|1222|8
SE 2024|1222|14
SE 2024|1222|15
SE 2024|1222|16
EVENTS_EOF
)

echo "meet,eref,diver" > "$OUT_CSV"

while IFS='|' read -r MEET MREF EREF; do
  [ -z "$MREF" ] && continue
  CACHE_FILE="$CACHE_DIR/sheet_${MREF}_${EREF}.html"
  if [ -f "$CACHE_FILE" ]; then
    echo "cached: $MEET (eref $EREF)"
  else
    echo "fetching: $MEET (eref $EREF)..."
    curl -s -A "Mozilla/5.0 (research script)" \
      "https://diverecorder.co.uk/meetexplorer/selectsheet.php?mref=${MREF}&eref=${EREF}" \
      -o "$CACHE_FILE"
    sleep 0.5
  fi

  # Parse guests out of this page's HTML and append to the CSV.
  python3 - "$CACHE_FILE" "$MEET" "$EREF" >> "$OUT_CSV" << 'PYEOF'
import sys, re, html

path, meet, eref = sys.argv[1], sys.argv[2], sys.argv[3]
page = open(path, encoding="utf-8", errors="replace").read()

for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
    cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells]
    cells = [c for c in cells if c != ""]
    if len(cells) < 2:
        continue
    rank, name = cells[0], cells[1]
    # guest rows have a parenthesised unofficial rank, e.g. "(3)"
    if re.match(r"^\(\d+\)$", rank) and "(Guest)" in name:
        clean_name = name.replace(" (Guest)", "").strip()
        print(f'"{meet}",{eref},"{clean_name}"')
PYEOF

done <<< "$EVENTS"

echo ""
echo "Done. Guests found:"
tail -n +2 "$OUT_CSV"
echo ""
echo "Send guests_2024.csv back."
