#!/bin/zsh

set -euo pipefail

repo_dir="${0:A:h:h}"
test_root="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/ardourton-test.XXXXXX")"
config_dir="${test_root}/Ardour9"
original_dir="${test_root}/original"
custom_dir="${test_root}/customized"

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
  [[ -f "${dest}/ardourton/receipt" ]]
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

run_install "${config_dir}"

assert_expected_files_installed "${config_dir}"
/usr/bin/xmllint --noout "${config_dir}/ui_config" "${config_dir}/ui_scripts"
/usr/bin/grep -q 'name="sentinel" value="preserve-me"' "${config_dir}/ui_config"
/usr/bin/grep -q 'name="unrelated-ui-option" value="keep-me"' "${config_dir}/ui_config"
/usr/bin/grep -q 'name="color-file" value="ardourton"' "${config_dir}/ui_config"
/usr/bin/grep -q 'BindingSet name="Ardourton macOS"' "${config_dir}/ardour.keys"
[[ ! -e "${config_dir}/ardour-9.7.bindings" ]]

# Receipt version matches the profile manifest.
/usr/bin/grep -q '^version=0\.2\.2$' "${config_dir}/ardourton/receipt"
/usr/bin/grep -q '^backup=' "${config_dir}/ardourton/receipt"
backup_path="$(/usr/bin/awk -F= '/^backup=/{print $2}' "${config_dir}/ardourton/receipt")"
[[ -d "${backup_path}" ]]

installed_payload="$(/usr/bin/sed -n 's#.*<ActionScript[^>]*>\([^<]*\)</ActionScript>.*#\1#p' "${config_dir}/ui_scripts")"
decoded="$(print -rn -- "${installed_payload}" | /usr/bin/base64 -D)"
[[ "${decoded}" == *"Ardourton: Add Stereo Audio Track"* ]]
[[ "${decoded}" == *"Unrelated User Action"* ]]

run_restore "${config_dir}"

/usr/bin/cmp "${original_dir}/ui_config" "${config_dir}/ui_config"
/usr/bin/cmp "${original_dir}/ui_scripts" "${config_dir}/ui_scripts"
/usr/bin/cmp "${original_dir}/ardour.keys" "${config_dir}/ardour.keys"
[[ "$(hash_file "${config_dir}/ui_config")" == "${ui_hash}" ]]
[[ "$(hash_file "${config_dir}/ui_scripts")" == "${scripts_hash}" ]]
[[ "$(hash_file "${config_dir}/ardour.keys")" == "${keys_hash}" ]]
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
[[ -f "${custom_dir}/themes/other.colors" ]]
/usr/bin/grep -q 'name="unrelated-ui-option" value="keep-me"' "${custom_dir}/ui_config"

run_restore "${custom_dir}"
/usr/bin/cmp "${custom_original}/ui_config" "${custom_dir}/ui_config"
/usr/bin/cmp "${custom_original}/ui_scripts" "${custom_dir}/ui_scripts"
/usr/bin/cmp "${custom_original}/ardour.keys" "${custom_dir}/ardour.keys"
[[ -f "${custom_dir}/themes/other.colors" ]]
[[ ! -e "${custom_dir}/themes/ardourton-ardour.colors" ]]
[[ ! -e "${custom_dir}/scripts/ardourton_beat_production.lua" ]]

print -- "macOS installer checks passed"
