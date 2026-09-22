#!/bin/bash
# collect_results.sh CASE [CASE ...] : copy the small, reportable files of each
# finished run into results/<CASE>/ so they can be committed to the repo.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
for CASE in "$@"; do
  W=$HOME/su2-work/$CASE
  [ -d "$W" ] || { echo "skip $CASE (no $W)"; continue; }
  D="$HERE/results/$CASE"; mkdir -p "$D"
  cp "$W"/STATUS "$D"/ 2>/dev/null
  cp "$W"/*.cfg "$D"/ 2>/dev/null
  cp "$W"/history_*.csv "$D"/ 2>/dev/null
  # final wall file only (surface CSVs can be many)
  last=$(ls -1 "$W"/wall_*.csv 2>/dev/null | tail -1); [ -n "$last" ] && cp "$last" "$D"/
  # check output, if it was run into the repo's results dir or the default one
  cp -r "$HERE/results_check/$CASE" "$D/check" 2>/dev/null
  cp "$W"/su2_phase1_summary.txt "$D"/ 2>/dev/null
  # last 200 lines of the solver log: enough to diagnose, small
  for l in "$W"/log_*.txt; do [ -f "$l" ] && tail -200 "$l" > "$D/$(basename "$l" .txt)_tail.txt"; done
  echo "$CASE -> $D  ($(du -sh "$D" | cut -f1))"
done
echo
echo "Now:  cd $HERE && git add -A results && git commit -m '...' && git push"
