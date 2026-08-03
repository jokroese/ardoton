#!/bin/zsh

set -euo pipefail

repo_dir="${0:A:h:h}"
test_root="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/ardourton-test.XXXXXX")"
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

  local_state=$'scripts = {}\nscripts[7] = { n = "Unrelated User Action", a = {}, f = "x", s = "" }'
  encoded="$(print -rn -- "${local_state}" | /usr/bin/base64 | /usr/bin/tr -d '\n')"
  {
    print -r -- '<?xml version="1.0" encoding="UTF-8"?>'
    print -r -- '<UIScripts>'
    print -r -- "  <ActionScript lua=\"Lua 5.3\">${encoded}</ActionScript>"
    print -r -- '  <ActionHooks/>'
    print -r -- '</UIScripts>'
  } > "${dest}/ui_scripts"

  print -r -- "original keymap" > "${dest}/ardour.keys"
  /bin/cp -p "${fixture_instant}" "${dest}/instant.xml"
}

assert_expected_files_installed () {
  local dest="$1"
  [[ -f "${dest}/themes/ardourton-ardour.colors" ]]
  [[ -f "${dest}/scripts/ardourton_beat_production.lua" ]]
  [[ -f "${dest}/scripts/ardourton_add_audio_track.lua" ]]
  [[ -f "${dest}/scripts/ardourton_add_midi_track.lua" ]]
  [[ -f "${dest}/scripts/ardourton_add_return.lua" ]]
  [[ -f "${dest}/scripts/ardourton_set_loop.lua" ]]
  [[ -f "${dest}/scripts/ardourton_duplicate_tracks.lua" ]]
  [[ -f "${dest}/ardour.keys" ]]
  [[ -f "${dest}/instant.xml" ]]
  [[ -f "${dest}/ardourton/receipt" ]]
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
  ARDOURTON_CONFIG_DIR="${dest}" \
  ARDOURTON_SKIP_PROCESS_CHECK=1 \
  ARDOURTON_SKIP_VERSION_CHECK=1 \
    "${repo_dir}/installer/macos.sh" install
}

run_restore () {
  local dest="$1"
  ARDOURTON_CONFIG_DIR="${dest}" \
  ARDOURTON_SKIP_PROCESS_CHECK=1 \
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
/usr/bin/grep -q 'name="color-file" value="ardourton"' "${config_dir}/ui_config"
/usr/bin/grep -q 'BindingSet name="Ardourton macOS"' "${config_dir}/ardour.keys"
[[ ! -e "${config_dir}/ardour-9.7.bindings" ]]
assert_grid_snap_defaults "${config_dir}"

# Receipt version matches the profile manifest.
/usr/bin/grep -q '^version=0\.2\.3$' "${config_dir}/ardourton/receipt"
/usr/bin/grep -q '^backup=' "${config_dir}/ardourton/receipt"
backup_path="$(/usr/bin/awk -F= '/^backup=/{print $2}' "${config_dir}/ardourton/receipt")"
[[ -d "${backup_path}" ]]
[[ -f "${backup_path}/files/instant.xml" ]]

installed_payload="$(/usr/bin/sed -n 's#.*<ActionScript[^>]*>\([^<]*\)</ActionScript>.*#\1#p' "${config_dir}/ui_scripts")"
decoded="$(print -rn -- "${installed_payload}" | /usr/bin/base64 -D)"
[[ "${decoded}" == *"Ardourton: Add Stereo Audio Track"* ]]
[[ "${decoded}" == *"Unrelated User Action"* ]]

run_restore "${config_dir}"

/usr/bin/cmp "${original_dir}/ui_config" "${config_dir}/ui_config"
/usr/bin/cmp "${original_dir}/ui_scripts" "${config_dir}/ui_scripts"
/usr/bin/cmp "${original_dir}/ardour.keys" "${config_dir}/ardour.keys"
/usr/bin/cmp "${original_dir}/instant.xml" "${config_dir}/instant.xml"
[[ "$(hash_file "${config_dir}/ui_config")" == "${ui_hash}" ]]
[[ "$(hash_file "${config_dir}/ui_scripts")" == "${scripts_hash}" ]]
[[ "$(hash_file "${config_dir}/ardour.keys")" == "${keys_hash}" ]]
[[ "$(hash_file "${config_dir}/instant.xml")" == "${instant_hash}" ]]
[[ ! -e "${config_dir}/themes/ardourton-ardour.colors" ]]
[[ ! -e "${config_dir}/scripts/ardourton_beat_production.lua" ]]
[[ ! -e "${config_dir}/ardourton/receipt" ]]

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
[[ ! -e "${custom_dir}/themes/ardourton-ardour.colors" ]]
[[ ! -e "${custom_dir}/scripts/ardourton_beat_production.lua" ]]

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

print -- "macOS installer checks passed"
