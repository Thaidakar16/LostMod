#!/bin/bash
# Build the mod, update the "live" patch, and optionally publish a numbered ship.
#
#   ./patch.sh [file.asm]            build + update docs/patches/live.bps
#   ./patch.sh --no-bps [file.asm]   build only, no patch
#   ./patch.sh --ship [file.asm]     build + live + ask for notes, publish a numbered ship
#   ./patch.sh --week                show the current Terra week
#   ./patch.sh --next-week           move the tracker to the next week

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"        # run from the script's own folder

CLEAN=LostMod_Private/rom/LostVikings.sfc
MOD=LostMod_Private/rom/LostVikingsM.sfc
DOCS=docs
STATE=.terra_week                          # week tracker (keep this out of the public repo)
EXPECTED_SHA256="9f7782a92fda789f9d119b1f0a2f7da0f35606357556a48eca9487797ee1a888"
MAX_PATCH=16384                            # warn if a patch is bigger than this (bytes)

# ---------- week tracker: prep2 -> prep3 -> week1 -> week2 -> ... ----------
[ -f "$STATE" ] || echo "prep2" > "$STATE"
week=$(<"$STATE")

next_week() {
  case "$1" in
    prep2) echo prep3 ;;
    prep3) echo week1 ;;
    week*) echo "week$(( ${1#week} + 1 ))" ;;
    *) echo "Unknown week '$1' in $STATE" >&2; return 1 ;;
  esac
}
week_label() {
  case "$1" in
    prep*) echo "Prep ${1#prep}" ;;
    week*) echo "Week ${1#week}" ;;
    *) echo "$1" ;;
  esac
}

# ---------- arguments ----------
make_bps=true
ship=false
action=""
asm_arg=""
for arg in "$@"; do
  case "$arg" in
    --no-bps)    make_bps=false ;;
    --ship)      ship=true ;;
    --week)      action=show ;;
    --next-week) action=next ;;
    -*)          echo "Unknown option: $arg"; exit 1 ;;
    *)           asm_arg="$arg" ;;
  esac
done

if [ "$action" = show ]; then
  echo "Current week: $(week_label "$week")"
  exit 0
fi
if [ "$action" = next ]; then
  week=$(next_week "$week")
  echo "$week" > "$STATE"
  echo "Now on $(week_label "$week")"
  exit 0
fi
if [ "$ship" = true ] && [ "$make_bps" = false ]; then
  echo "--ship needs a patch, so it can't be combined with --no-bps."
  exit 1
fi

# ---------- make sure the clean ROM is the one the site expects ----------
if [ "$make_bps" = true ]; then
  actual=$(sha256sum "$CLEAN" | cut -d' ' -f1)
  if [ "$actual" != "$EXPECTED_SHA256" ]; then
    echo "ERROR: $CLEAN is not the ROM the site expects (hash mismatch)."
    echo "       Patches made from it wouldn't work on the site. Is it headerless?"
    exit 1
  fi
fi

# ---------- build (your original steps) ----------
src="mod/${asm_arg:-bank_80.asm}"
cp "$CLEAN" "$MOD"
asar "$src" "$MOD"
echo "Built $MOD from $src"

[ "$make_bps" = true ] || exit 0

# ---------- live patch ----------
mkdir -p "$DOCS/patches"
LIVE="$DOCS/patches/live.bps"
flips --create --bps-delta "$CLEAN" "$MOD" "$LIVE"
size=$(stat -c %s "$LIVE")
echo "live.bps: $size bytes"

# round trip: applying the patch to the clean ROM must give back the exact build
VERIFY=LostMod_Private/rom/.verify.sfc
rm -f "$VERIFY"
flips --apply "$LIVE" "$CLEAN" "$VERIFY" > /dev/null
if cmp -s "$VERIFY" "$MOD"; then
  echo "Patch verified (rebuilds the mod byte for byte)."
  rm -f "$VERIFY"
else
  rm -f "$VERIFY"
  echo "ERROR: the patch does not rebuild the mod exactly. Not publishing it."
  exit 1
fi

too_big=false
if [ "$size" -gt "$MAX_PATCH" ]; then
  too_big=true
  echo "WARNING: that's bigger than expected ($size > $MAX_PATCH bytes)."
  echo "         It may be carrying original game code. Check before pushing."
fi

[ "$ship" = true ] || exit 0

# ---------- numbered ship ----------
echo
echo "Current week: $(week_label "$week")"
read -rp "Press Enter to keep it, or type 'next' to move to $(week_label "$(next_week "$week")"): " answer
if [ "$answer" = next ]; then
  week=$(next_week "$week")
  echo "$week" > "$STATE"
fi
read -rp "Notes for this ship: " notes
if [ -z "$notes" ]; then
  echo "Notes can't be empty. Live patch is updated, but no ship was published."
  exit 1
fi
if [ "$too_big" = true ]; then
  read -rp "The patch is large. Publish it as a ship anyway? [y/N] " yn
  [ "$yn" = y ] || { echo "Not published."; exit 1; }
fi

# add the entry to ships.json; the version number is the count so far this week, plus one
id=$(python3 - "$DOCS/ships.json" "$week" "$(week_label "$week")" "$notes" <<'PY'
import json, os, sys
path, key, label, notes = sys.argv[1:5]
ships = json.load(open(path)) if os.path.exists(path) else []
version = 1 + sum(1 for s in ships if s.get("id", "").startswith(key + "-"))
sid = f"{key}-{version}"
ships.append({"id": sid, "week": label, "version": version, "notes": notes})
with open(path, "w") as f:
    json.dump(ships, f, indent=2)
    f.write("\n")
print(sid)
PY
)
cp "$LIVE" "$DOCS/patches/$id.bps"

echo
echo "Published $id ($(week_label "$week"), $notes)"
echo "Next: add screenshots to $DOCS/media and a \"media\" list to its entry in ships.json,"
echo "      then commit and push the docs repo."