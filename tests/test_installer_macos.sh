#!/bin/zsh

set -euo pipefail

repo_dir="${0:A:h:h}"
test_root="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/ardoton-test.XXXXXX")"
config_dir="${test_root}/Ardour9"
original_dir="${test_root}/original"
custom_dir="${test_root}/customized"
fixture_instant="${repo_dir}/tests/fixtures/config/instant.xml"

cleanup () {
  /bin/rm -rf "${test_root}"
}
trap cleanup EXIT

hash_file () {
  /usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}'
}

decode_ui_scripts () {
  local encoded
  encoded="$(/usr/bin/sed -n 's#.*<ActionScript[^>]*>\([^<]*\)</ActionScript>.*#\1#p' "$1")"
  print -rn -- "${encoded}" | /usr/bin/base64 -D
}

write_ui_scripts_payload () {
  local dest="$1"
  local body="$2"
  local encoded
  encoded="$(print -rn -- "${body}" | /usr/bin/base64 | /usr/bin/tr -d '\n')"
  {
    print -r -- '<?xml version="1.0" encoding="UTF-8"?>'
    print -r -- '<UIScripts>'
    print -r -- "  <ActionScript lua=\"Lua 5.3\">${encoded}</ActionScript>"
    print -r -- '  <ActionHooks/>'
    print -r -- '</UIScripts>'
  } > "${dest}/ui_scripts"
}

# A stand-in for one entry in Ardour's decoded ui_scripts table, in the table-constructor
# form a hand-written or older payload uses. The installer's own fragment uses the flat
# `scripts[N]["k"] = v` form instead, so between them the two cover both shapes.
user_action_entry () {
  print -rn -- "scripts[$1] = { n = \"$2\", a = {}, f = \"x\", s = \"\" }"
}

write_stock_fixture () {
  local dest="$1"
  /bin/mkdir -p "${dest}"

  {
    print -r -- '<?xml version="1.0" encoding="UTF-8"?>'
    print -r -- '<Ardour>'
    print -r -- '  <UI>'
    print -r -- '    <Option name="flat-buttons" value="0"/>'
    print -r -- '    <Option name="show-secondary-clock" value="1"/>'
    print -r -- '    <Option name="sentinel" value="preserve-me"/>'
    print -r -- '    <Option name="unrelated-ui-option" value="keep-me"/>'
    print -r -- '  </UI>'
    print -r -- '  <Canvas/>'
    print -r -- '</Ardour>'
  } > "${dest}/ui_config"

  write_ui_scripts_payload "${dest}" \
    "scripts = {}"$'\n'"$(user_action_entry 7 'Unrelated User Action')"

  print -r -- "original keymap" > "${dest}/ardour.keys"
  /bin/cp -p "${fixture_instant}" "${dest}/instant.xml"
}

# --- Refused-install helpers ---------------------------------------------------------

config_fingerprint () {
  local dest="$1"
  local name
  for name in ardour.keys ui_config ui_scripts instant.xml; do
    print -r -- "${name} $(hash_file "${dest}/${name}")"
  done
}

# A refused install must leave nothing behind: no mutated config, no copied payload, no
# receipt, and no backup -- the point of preflighting is that recovery is not needed.
assert_install_refused () {
  local dest="$1"
  local before="$2"
  local after
  after="$(config_fingerprint "${dest}")"
  if [[ "${after}" != "${before}" ]]; then
    print -u2 -- "refused install mutated ${dest}:"
    print -u2 -- "before: ${before}"
    print -u2 -- "after:  ${after}"
    return 1
  fi
  [[ ! -e "${dest}/themes/ardoton-ardour.colors" ]]
  [[ ! -e "${dest}/scripts/ardoton_beat_production.lua" ]]
  [[ ! -e "${dest}/scripts/ardoton_duplicate_time.lua" ]]
  [[ ! -e "${dest}/ardoton/receipt" ]]
  [[ ! -e "${dest}/ardoton/backups" ]]
}

install_must_fail () {
  local dest="$1"
  shift
  # `status` is a read-only alias for $? in zsh; name the local something else.
  local output exit_code needle
  set +e
  output="$(run_install "${dest}" 2>&1)"
  exit_code=$?
  set -e
  if (( exit_code == 0 )); then
    print -u2 -- "expected install to fail for ${dest}, but it succeeded"
    return 1
  fi
  for needle in "$@"; do
    if [[ "${output}" != *"${needle}"* ]]; then
      print -u2 -- "install failure message for ${dest} is missing '${needle}':"
      print -u2 -- "${output}"
      return 1
    fi
  done
}

# Every slot/name pair the shipped fragment declares must survive into the installed
# payload -- not just the one display name the installer used to look for.
assert_all_ardoton_slots_installed () {
  local dest="$1"
  local fragment="${repo_dir}/profile/ui-scripts/ardoton-actions.lua-state"
  local decoded pair
  decoded="$(decode_ui_scripts "${dest}/ui_scripts")"

  local -a pairs
  pairs=(${(f)"$(/usr/bin/sed -E -n 's/.*(scripts\[[0-9]+\]\["n"\] = "[^"]*").*/\1/p' "${fragment}")"})
  if (( ${#pairs} != 16 )); then
    print -u2 -- "expected 16 slot/name pairs in the fragment, found ${#pairs}"
    return 1
  fi
  for pair in "${pairs[@]}"; do
    if [[ "${decoded}" != *"${pair}"* ]]; then
      print -u2 -- "installed payload is missing: ${pair}"
      return 1
    fi
  done

  local -a slots
  slots=(${(f)"$(print -rl -- "${pairs[@]}" |
    /usr/bin/sed -E 's/^scripts\[([0-9]+)\].*/\1/' | /usr/bin/sort -n)"})
  if [[ "${slots[1]}" != "17" || "${slots[-1]}" != "32" ]]; then
    print -u2 -- "fragment no longer spans slots 17-32: ${slots[*]}"
    return 1
  fi
}

assert_expected_files_installed () {
  local dest="$1"
  [[ -f "${dest}/themes/ardoton-ardour.colors" ]]
  [[ -f "${dest}/scripts/ardoton_beat_production.lua" ]]
  [[ -f "${dest}/scripts/ardoton_add_audio_track.lua" ]]
  [[ -f "${dest}/scripts/ardoton_add_midi_track.lua" ]]
  [[ -f "${dest}/scripts/ardoton_add_return.lua" ]]
  [[ -f "${dest}/scripts/ardoton_set_loop.lua" ]]
  [[ -f "${dest}/scripts/ardoton_duplicate_tracks.lua" ]]
  [[ -f "${dest}/ardour.keys" ]]
  [[ -f "${dest}/instant.xml" ]]
  [[ -f "${dest}/ardoton/receipt" ]]
}

assert_grid_snap_defaults () {
  local dest="$1"
  /usr/bin/grep -q 'name="snap-threshold" value="10"' "${dest}/ui_config"
  /usr/bin/grep -q 'name="ruler-granularity" value="250"' "${dest}/ui_config"
  /usr/bin/grep -q 'name="snap-target" value="SnapTargetBoth"' "${dest}/ui_config"
  /usr/bin/grep -q 'name="rulers-follow-grid" value="1"' "${dest}/ui_config"

  /usr/bin/grep -q '<Editor [^>]*grid-type="GridTypeBeatDiv32"' "${dest}/instant.xml"
  /usr/bin/grep -q '<Editor [^>]*snap-mode="SnapMagnetic"' "${dest}/instant.xml"
  /usr/bin/grep -q '<MIDICueEditor [^>]*grid-type="GridTypeBeatDiv32"' "${dest}/instant.xml"
  /usr/bin/grep -q '<MIDICueEditor [^>]*snap-mode="SnapMagnetic"' "${dest}/instant.xml"
  /usr/bin/grep -q 'playhead="319216"' "${dest}/instant.xml"
  /usr/bin/grep -q 'pre-internal-grid-type="GridTypeBeat"' "${dest}/instant.xml"
  /usr/bin/grep -q '<AudioClipEditor [^>]*grid-type="GridTypeMinSec"' "${dest}/instant.xml"
}

run_install () {
  local dest="$1"
  ARDOTON_CONFIG_DIR="${dest}" \
  ARDOTON_SKIP_PROCESS_CHECK=1 \
  ARDOTON_SKIP_VERSION_CHECK=1 \
    "${repo_dir}/installer/macos.sh" install
}

run_restore () {
  local dest="$1"
  ARDOTON_CONFIG_DIR="${dest}" \
  ARDOTON_SKIP_PROCESS_CHECK=1 \
    "${repo_dir}/installer/macos.sh" restore
}

# --- Fresh temporary configuration ---
write_stock_fixture "${config_dir}"
/bin/cp -R "${config_dir}" "${original_dir}"

ui_hash="$(hash_file "${config_dir}/ui_config")"
scripts_hash="$(hash_file "${config_dir}/ui_scripts")"
keys_hash="$(hash_file "${config_dir}/ardour.keys")"
instant_hash="$(hash_file "${config_dir}/instant.xml")"

run_install "${config_dir}"

assert_expected_files_installed "${config_dir}"
/usr/bin/xmllint --noout "${config_dir}/ui_config" "${config_dir}/ui_scripts" "${config_dir}/instant.xml"
/usr/bin/grep -q 'name="sentinel" value="preserve-me"' "${config_dir}/ui_config"
/usr/bin/grep -q 'name="unrelated-ui-option" value="keep-me"' "${config_dir}/ui_config"
/usr/bin/grep -q 'name="color-file" value="ardoton"' "${config_dir}/ui_config"
/usr/bin/grep -q 'BindingSet name="Ardoton macOS"' "${config_dir}/ardour.keys"
[[ ! -e "${config_dir}/ardour-9.7.bindings" ]]
assert_grid_snap_defaults "${config_dir}"

# Receipt version matches the profile manifest.
/usr/bin/grep -q '^version=0\.2\.5$' "${config_dir}/ardoton/receipt"
/usr/bin/grep -q '^backup=' "${config_dir}/ardoton/receipt"
backup_path="$(/usr/bin/awk -F= '/^backup=/{print $2}' "${config_dir}/ardoton/receipt")"
[[ -d "${backup_path}" ]]
[[ -f "${backup_path}/files/instant.xml" ]]

decoded="$(decode_ui_scripts "${config_dir}/ui_scripts")"
[[ "${decoded}" == *"Unrelated User Action"* ]]
[[ "${decoded}" == *'scripts[7] ='* ]]
assert_all_ardoton_slots_installed "${config_dir}"

run_restore "${config_dir}"

/usr/bin/cmp "${original_dir}/ui_config" "${config_dir}/ui_config"
/usr/bin/cmp "${original_dir}/ui_scripts" "${config_dir}/ui_scripts"
/usr/bin/cmp "${original_dir}/ardour.keys" "${config_dir}/ardour.keys"
/usr/bin/cmp "${original_dir}/instant.xml" "${config_dir}/instant.xml"
[[ "$(hash_file "${config_dir}/ui_config")" == "${ui_hash}" ]]
[[ "$(hash_file "${config_dir}/ui_scripts")" == "${scripts_hash}" ]]
[[ "$(hash_file "${config_dir}/ardour.keys")" == "${keys_hash}" ]]
[[ "$(hash_file "${config_dir}/instant.xml")" == "${instant_hash}" ]]
[[ ! -e "${config_dir}/themes/ardoton-ardour.colors" ]]
[[ ! -e "${config_dir}/scripts/ardoton_beat_production.lua" ]]
[[ ! -e "${config_dir}/ardoton/receipt" ]]

# --- Install over a representative customized fixture ---
write_stock_fixture "${custom_dir}"
print -r -- "customized keymap body" > "${custom_dir}/ardour.keys"
/bin/mkdir -p "${custom_dir}/themes"
print -r -- "preexisting theme" > "${custom_dir}/themes/other.colors"
custom_original="${test_root}/custom-original"
/bin/cp -R "${custom_dir}" "${custom_original}"

run_install "${custom_dir}"
assert_expected_files_installed "${custom_dir}"
assert_grid_snap_defaults "${custom_dir}"
[[ -f "${custom_dir}/themes/other.colors" ]]
/usr/bin/grep -q 'name="unrelated-ui-option" value="keep-me"' "${custom_dir}/ui_config"

run_restore "${custom_dir}"
/usr/bin/cmp "${custom_original}/ui_config" "${custom_dir}/ui_config"
/usr/bin/cmp "${custom_original}/ui_scripts" "${custom_dir}/ui_scripts"
/usr/bin/cmp "${custom_original}/ardour.keys" "${custom_dir}/ardour.keys"
/usr/bin/cmp "${custom_original}/instant.xml" "${custom_dir}/instant.xml"
[[ -f "${custom_dir}/themes/other.colors" ]]
[[ ! -e "${custom_dir}/themes/ardoton-ardour.colors" ]]
[[ ! -e "${custom_dir}/scripts/ardoton_beat_production.lua" ]]

# --- Absent instant.xml creates a stub with target defaults ---
absent_dir="${test_root}/absent-instant"
write_stock_fixture "${absent_dir}"
/bin/rm -f "${absent_dir}/instant.xml"
run_install "${absent_dir}"
[[ -f "${absent_dir}/instant.xml" ]]
/usr/bin/xmllint --noout "${absent_dir}/instant.xml"
/usr/bin/grep -q '<Editor grid-type="GridTypeBeatDiv32" snap-mode="SnapMagnetic"/>' "${absent_dir}/instant.xml"
run_restore "${absent_dir}"
[[ ! -e "${absent_dir}/instant.xml" ]]

# --- Occupied Ardoton slots are refused before anything is touched ---
#
# Ardoton owns Lua action slots 17-32 while installed. There is no dynamic relocation:
# if any of those slots is already assigned, the install must abort before it can silently
# replace a user's own action. The supported upgrade path is restore-then-install.

collision_case () {
  local label="$1"
  shift
  local body="$1"
  shift
  local case_dir="${test_root}/collision-${label}"
  write_stock_fixture "${case_dir}"
  write_ui_scripts_payload "${case_dir}" "${body}"
  local before
  before="$(config_fingerprint "${case_dir}")"
  install_must_fail "${case_dir}" "$@"
  assert_install_refused "${case_dir}" "${before}"
}

collision_case slot17 \
  "scripts = {}"$'\n'"$(user_action_entry 17 'My Own Action')" \
  "17"

collision_case slot28 \
  "scripts = {}"$'\n'"$(user_action_entry 28 'My Own Action')" \
  "28"

collision_case slot17-and-32 \
  "scripts = {}"$'\n'"$(user_action_entry 17 'First')"$'\n'"$(user_action_entry 32 'Last')" \
  "17" "32"

# A stale Ardoton payload with no receipt is indistinguishable from a user action, and is
# refused for the same reason: the installer must not decide on its own what to overwrite.
collision_case stale-ardoton \
  "scripts = {}"$'\n'"$(user_action_entry 28 'Ardoton: Add Stereo Audio Track')"$'\n'"$(user_action_entry 29 'Ardoton: Add MIDI Track')"$'\n'"$(user_action_entry 30 'Ardoton: Add Return')"$'\n'"$(user_action_entry 31 'Ardoton: Set and Toggle Loop')"$'\n'"$(user_action_entry 32 'Ardoton: Duplicate Tracks')" \
  "28" "29" "30" "31" "32"

collision_case partial-ardoton \
  "scripts = {}"$'\n'"$(user_action_entry 17 'Ardoton: Duplicate Time')"$'\n'"$(user_action_entry 20 'Ardoton: Lengthen Loop')"$'\n'"$(user_action_entry 28 'Ardoton: Add Stereo Audio Track')" \
  "17" "20" "28"

# The serialized form Ardour itself writes must be detected too, not only the
# table-constructor form above.
collision_case serialized-form \
  'scripts[19] = {} scripts[19]["n"] = "Someone Else" scripts[19]["a"] = {} scripts[19]["f"] = "x" scripts[19]["s"] = ""' \
  "19"

# --- An undecodable payload is refused rather than silently replaced ---
malformed_dir="${test_root}/malformed"
write_stock_fixture "${malformed_dir}"
{
  print -r -- '<?xml version="1.0" encoding="UTF-8"?>'
  print -r -- '<UIScripts>'
  print -r -- '  <ActionScript lua="Lua 5.3">!!!not@@base64###</ActionScript>'
  print -r -- '  <ActionHooks/>'
  print -r -- '</UIScripts>'
} > "${malformed_dir}/ui_scripts"
malformed_before="$(config_fingerprint "${malformed_dir}")"
install_must_fail "${malformed_dir}" "ui_scripts"
assert_install_refused "${malformed_dir}" "${malformed_before}"

# --- Slots outside 17-32 are still fine, and survive byte-for-byte ---
free_dir="${test_root}/free-slots"
write_stock_fixture "${free_dir}"
write_ui_scripts_payload "${free_dir}" \
  "scripts = {}"$'\n'"$(user_action_entry 1 'User One')"$'\n'"$(user_action_entry 16 'User Sixteen')"
run_install "${free_dir}"
assert_expected_files_installed "${free_dir}"
assert_all_ardoton_slots_installed "${free_dir}"
free_decoded="$(decode_ui_scripts "${free_dir}/ui_scripts")"
[[ "${free_decoded}" == *"$(user_action_entry 1 'User One')"* ]]
[[ "${free_decoded}" == *"$(user_action_entry 16 'User Sixteen')"* ]]

# --- Installing twice over an Ardoton payload is refused, not doubled ---
# The receipt check catches the normal case; deleting the receipt leaves the stale-payload
# check as the backstop.
/bin/rm -f "${free_dir}/ardoton/receipt"
free_before="$(config_fingerprint "${free_dir}")"
install_must_fail "${free_dir}" "17" "32"
free_after="$(config_fingerprint "${free_dir}")"
[[ "${free_after}" == "${free_before}" ]]

print -- "macOS installer checks passed"
